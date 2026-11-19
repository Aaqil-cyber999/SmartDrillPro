"""Import, validate, classify and parse PCB manufacturing files.

The service owns the flow from a user-selected file/folder/ZIP to metadata in
``project.json``. Geometry itself stays in memory; the viewer and CAM stages
re-parse the untouched files under ``source/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import tempfile
import zipfile

from app.core.project_manager import ProjectManager
from app.file_processing.excellon_parser import ExcellonParser
from app.file_processing.file_validator import validate_file
from app.file_processing.gerber_parser import GerberParser
from app.file_processing.layer_classifier import classify_layer
from app.models.parsed_layer import ParsedLayer
from app.models.pcb_project import PcbProject, SourceFile

MAX_IMPORT_BYTES = 64 * 1024 * 1024


@dataclass
class ImportOutcome:
    added: list[SourceFile] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    parsed: dict[str, ParsedLayer] = field(default_factory=dict)


class ImportService:
    def __init__(self, projects: ProjectManager) -> None:
        self.projects = projects
        self.gerber_parser = GerberParser()
        self.excellon_parser = ExcellonParser()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def import_paths(self, paths: list[Path]) -> ImportOutcome:
        outcome = ImportOutcome()
        if self.projects.active is None:
            outcome.errors.append("Create or open a project before importing files.")
            return outcome

        with tempfile.TemporaryDirectory(prefix="smartdrill-import-") as staging_name:
            staging = Path(staging_name)
            candidates = self._expand(paths, staging, outcome)
            accepted: list[Path] = []
            for path in candidates:
                result = validate_file(path)
                if not result.valid:
                    outcome.skipped.append(f"{path.name}: {'; '.join(result.errors)}")
                    continue
                if result.content_type not in {"gerber", "excellon"}:
                    outcome.skipped.append(f"{path.name}: not a Gerber or Excellon file")
                    continue
                if path.stat().st_size > MAX_IMPORT_BYTES:
                    outcome.skipped.append(f"{path.name}: larger than the {MAX_IMPORT_BYTES // 1024 // 1024} MB import limit")
                    continue
                accepted.append(path)

            if not accepted:
                return outcome

            added, skipped = self.projects.add_source_files(accepted)
            outcome.added.extend(added)
            outcome.skipped.extend(skipped)

            source_dir = self.projects.active_dir_or_raise / "source"
            for record in added:
                file_path = source_dir / record.name
                try:
                    self._describe(record, file_path, outcome)
                except (OSError, ValueError, SyntaxError, TypeError, IndexError) as exc:
                    record.warnings.append(f"Parse failed: {exc}")
                    outcome.errors.append(f"{record.name}: {exc}")

            self.projects.save()
            self.projects.events.emit("layers_changed", self.projects.active)
        return outcome

    def parse_project(self, project: PcbProject | None = None, project_dir: Path | None = None) -> dict[str, ParsedLayer]:
        """Re-parse every valid source file. Used by the viewer and CAM stages."""
        project = project or self.projects.active
        if project is None:
            return {}
        project_dir = project_dir or self.projects.active_dir
        if project_dir is None:
            return {}
        parsed: dict[str, ParsedLayer] = {}
        for record in project.source_files:
            path = project_dir / record.relative_path
            if not path.is_file():
                continue
            try:
                if record.content_type == "gerber":
                    parsed[record.name] = self.gerber_parser.parse(path)
                elif record.content_type == "excellon":
                    parsed[record.name] = self.excellon_parser.parse(path)
            except (OSError, ValueError, SyntaxError, TypeError):
                continue
        return parsed

    def set_layer_role(self, name: str, role: str, confidence: float = 1.0, reason: str = "manual override") -> bool:
        project = self.projects.active
        if project is None:
            return False
        changed = False
        for record in project.source_files:
            if record.name != name:
                continue
            record.layer_role = role
            record.layer_confidence = confidence
            record.layer_reason = reason
            changed = True
        for layer in project.layers:
            if layer.get("file") == name:
                layer.update(role=role, confidence=confidence, source="manual", reason=reason)
                changed = True
        if changed:
            self.projects.save()
            self.projects.events.emit("layers_changed", project)
        return changed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _describe(self, record: SourceFile, path: Path, outcome: ImportOutcome) -> None:
        validation = validate_file(path)
        classification = classify_layer(record.name, validation)
        if validation.content_type == "gerber":
            parsed = self.gerber_parser.parse(path)
        elif validation.content_type == "excellon":
            parsed = self.excellon_parser.parse(path)
        else:
            raise ValueError(f"Unsupported content type: {validation.content_type}")

        record.content_type = validation.content_type
        record.layer_role = classification.role
        record.layer_confidence = round(classification.confidence, 2)
        record.layer_reason = classification.reason
        record.bounds = [round(value, 4) for value in parsed.bounds] if parsed.bounds else []
        record.feature_count = parsed.feature_count
        record.drill_tools = [tool.to_dict() for tool in parsed.drill_tools]
        record.warnings = list(dict.fromkeys(validation.warnings + parsed.warnings))
        outcome.parsed[record.name] = parsed

        self.projects.active.layers.append({
            "file": record.name,
            "role": record.layer_role,
            "confidence": record.layer_confidence,
            "source": "auto",
            "reason": record.layer_reason,
            "bounds": record.bounds,
            "feature_count": record.feature_count,
            "drill_tools": record.drill_tools,
        })

    def _expand(self, paths: list[Path], staging: Path, outcome: ImportOutcome) -> list[Path]:
        expanded: list[Path] = []
        for path in paths:
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file() and not self._ignored(child):
                        expanded.append(child)
                continue
            if not path.is_file():
                outcome.errors.append(f"Not a file: {path}")
                continue
            if zipfile.is_zipfile(path):
                expanded.extend(self._unzip(path, staging, outcome))
                continue
            expanded.append(path)
        return expanded

    @staticmethod
    def _ignored(path: Path) -> bool:
        return path.name.startswith(".") or "__MACOSX" in path.parts

    @staticmethod
    def _unzip(archive: Path, staging: Path, outcome: ImportOutcome) -> list[Path]:
        extracted: list[Path] = []
        try:
            with zipfile.ZipFile(archive) as bundle:
                for info in bundle.infolist():
                    if info.is_dir():
                        continue
                    # Sanitize entry names: ZIP paths must never escape the staging folder.
                    safe = Path(info.filename.replace("\\", "/")).name
                    if not safe or safe.startswith("."):
                        continue
                    destination = staging / f"{archive.stem}__{safe}"
                    with bundle.open(info) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target, length=1024 * 1024)
                    extracted.append(destination)
        except (OSError, zipfile.BadZipFile) as exc:
            outcome.errors.append(f"Could not read {archive.name}: {exc}")
        return extracted

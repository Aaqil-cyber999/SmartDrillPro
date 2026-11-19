"""Select layers, run the FlatCAM worker and persist job results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.cam.cam_settings import CamSettings, load_cam_settings, save_cam_settings
from app.cam.flatcam_adapter import CamOperation, FlatcamAdapter, FlatcamResult
from app.models.pcb_project import PcbProject

if TYPE_CHECKING:
    from app.core.application import Application


@dataclass
class CamRunResult:
    flatcam: FlatcamResult | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return bool(self.flatcam and self.flatcam.success and not self.errors)


class CamService:
    def __init__(self, core: "Application") -> None:
        self.core = core
        self.adapter = FlatcamAdapter(core.settings.flatcam_python, core.settings.flatcam_root)

    def settings_path(self, project_dir: Path) -> Path:
        return project_dir / "generated" / "cam_settings.json"

    def load_settings(self, project_dir: Path) -> CamSettings:
        return load_cam_settings(self.settings_path(project_dir))

    def save_settings(self, project_dir: Path, settings: CamSettings) -> None:
        save_cam_settings(self.settings_path(project_dir), settings)

    def plan(self, project: PcbProject, project_dir: Path, settings: CamSettings) -> tuple[list[CamOperation], list[str]]:
        """Map classified layers to FlatCAM operations. No hardcoded G-code."""
        source_dir = project_dir / "source"
        by_role: dict[str, list[Path]] = {}
        for record in project.source_files:
            by_role.setdefault(record.layer_role, []).append(source_dir / record.name)

        operations: list[CamOperation] = []
        warnings: list[str] = []
        gcode_dir = project_dir / "generated" / "gcode"
        gcode_dir.mkdir(parents=True, exist_ok=True)

        if settings.isolation_enabled:
            copper = by_role.get("top_copper") or by_role.get("bottom_copper") or []
            if copper:
                operations.append(CamOperation(
                    "isolation", copper[0], gcode_dir / "isolation.nc", "isolation"
                ))
            else:
                warnings.append("Isolation skipped: no top or bottom copper layer was detected.")

        if settings.drilling_enabled:
            drills = (
                by_role.get("plated_drill", [])
                + by_role.get("nonplated_drill", [])
                + by_role.get("drill", [])
            )
            if drills:
                for index, drill in enumerate(drills):
                    operations.append(CamOperation(
                        "drilling", drill, gcode_dir / f"drilling_{index + 1}.nc", f"drill{index + 1}"
                    ))
            else:
                warnings.append("Drilling skipped: no Excellon drill layer was detected.")

        if settings.outline_enabled:
            outline = by_role.get("outline") or []
            if outline:
                operations.append(CamOperation(
                    "outline", outline[0], gcode_dir / "outline.nc", "outline"
                ))
            else:
                warnings.append("Outline skipped: no outline/Edge_Cuts layer was detected.")

        missing = [str(op.source_path) for op in operations if not op.source_path.is_file()]
        if missing:
            warnings.append("Source files missing: " + ", ".join(missing))
            operations = [op for op in operations if op.source_path.is_file()]
        return operations, warnings

    def run(self, settings: CamSettings | None = None, timeout_s: int = 300) -> CamRunResult:
        project = self.core.projects.active
        project_dir = self.core.projects.active_dir
        if project is None or project_dir is None:
            return CamRunResult(errors=["Create or open a project first."])

        settings = settings or self.load_settings(project_dir)
        try:
            settings.validate()
        except ValueError as exc:
            return CamRunResult(errors=[str(exc)])

        operations, warnings = self.plan(project, project_dir, settings)
        if not operations:
            return CamRunResult(errors=warnings or ["No CAM operations were selected."])

        generated = project_dir / "generated"
        generated.mkdir(parents=True, exist_ok=True)
        for output in (op.output_path for op in operations):
            if output.exists():
                output.unlink()

        script = self.adapter.build_script(operations, settings)
        (generated / "flatcam_job.tcl").write_text(script, encoding="utf-8")
        result = self.adapter.run(script, generated, timeout_s=timeout_s)

        errors = list(warnings) + list(result.errors)
        job = {
            "id": datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "settings": settings.to_dict(),
            "operations": [
                {"kind": op.kind, "source": op.source_path.name, "gcode": op.output_path.name}
                for op in operations
            ],
            "success": result.success,
            "errors": errors,
            "stdout_tail": result.stdout[-2000:],
        }
        project.cam_jobs.append(job)
        self.core.projects.save()
        self.core.events.emit("cam_jobs_changed", project)
        return CamRunResult(result, errors)

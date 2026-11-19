"""Create, open, save and list projects."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from app.core.event_manager import EventManager
from app.models.pcb_project import (
    PcbProject,
    SourceFile,
    project_directory,
    project_metadata_path,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProjectManager:
    def __init__(self, projects_dir: Path, events: EventManager) -> None:
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.events = events
        self.active: PcbProject | None = None
        self.active_dir: Path | None = None

    @property
    def active_dir_or_raise(self) -> Path:
        if self.active is None or self.active_dir is None:
            raise RuntimeError("Open or create a project first.")
        return self.active_dir

    def create_project(self, name: str) -> tuple[PcbProject, Path]:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Project name cannot be empty.")

        project = PcbProject(name=cleaned)
        project_dir = project_directory(self.projects_dir, project)
        if project_dir.exists():
            raise ValueError(f"A project with this name already exists: {project_dir.name}")

        for folder in ("source", "generated", "history"):
            (project_dir / folder).mkdir(parents=True)
        (project_dir / "generated" / "gcode").mkdir()
        self.save(project, project_dir)
        self.set_active(project, project_dir)
        self.events.emit("project_created", project)
        return project, project_dir

    def list_projects(self) -> list[tuple[PcbProject, Path]]:
        projects: list[tuple[PcbProject, Path]] = []
        for metadata in sorted(self.projects_dir.glob("*/project.json")):
            try:
                project = self.load(metadata.parent)
                projects.append((project, metadata.parent))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return projects

    def load(self, project_dir: Path) -> PcbProject:
        metadata = project_metadata_path(project_dir)
        if not metadata.is_file():
            raise ValueError(f"Not a SmartDrill project: {project_dir}")
        data = json.loads(metadata.read_text(encoding="utf-8"))
        project = PcbProject.from_dict(data)
        if project.format_version != 1:
            raise ValueError(f"Unsupported project format version: {project.format_version}")
        return project

    def open_project(self, project_dir: Path) -> PcbProject:
        project = self.load(project_dir)
        self.set_active(project, project_dir)
        self.events.emit("project_opened", project)
        return project

    def save(self, project: PcbProject | None = None, project_dir: Path | None = None) -> None:
        project = project or self.active
        if project is None:
            return
        project_dir = project_dir or self.active_dir
        if project_dir is None:
            raise RuntimeError("No project directory is available.")
        project.touch()
        metadata = project_metadata_path(project_dir)
        temporary = metadata.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(project.to_dict(), indent=2), encoding="utf-8")
        temporary.replace(metadata)

    def set_active(self, project: PcbProject, project_dir: Path) -> None:
        self.active = project
        self.active_dir = project_dir
        self.events.emit("project_changed", project)

    def add_source_files(self, paths: list[Path]) -> tuple[list[SourceFile], list[str]]:
        """Copy files into the active project. Content validation comes in Phase 3."""
        project_dir = self.active_dir_or_raise
        source_dir = project_dir / "source"
        added: list[SourceFile] = []
        skipped: list[str] = []

        existing_hashes = {item.sha256 for item in self.active.source_files}
        existing_names = {item.name.lower() for item in self.active.source_files}

        for path in paths:
            if not path.is_file():
                skipped.append(f"{path.name}: not a file")
                continue
            checksum = file_sha256(path)
            if checksum in existing_hashes:
                skipped.append(f"{path.name}: identical file already imported")
                continue
            if path.name.lower() in existing_names:
                skipped.append(f"{path.name}: a file with this name already exists")
                continue

            destination = source_dir / path.name
            if destination.exists():
                skipped.append(f"{path.name}: destination already exists")
                continue

            shutil.copy2(path, destination)
            record = SourceFile(
                name=path.name,
                relative_path=str(destination.relative_to(project_dir)),
                size_bytes=destination.stat().st_size,
                sha256=checksum,
            )
            self.active.source_files.append(record)
            existing_hashes.add(checksum)
            existing_names.add(path.name.lower())
            added.append(record)

        if added:
            self.save()
            self.events.emit("files_added", self.active, added)
        return added, skipped

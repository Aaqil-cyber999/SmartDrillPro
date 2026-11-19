"""Project data model (Phase 2 subset).

A project is a folder on disk plus a project.json metadata file. Original
uploaded manufacturing files are copied into ``source/`` and never modified.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid

PROJECT_FORMAT_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


@dataclass
class SourceFile:
    """Record of one uploaded file. Layer roles are added in Phase 3."""

    name: str
    relative_path: str
    size_bytes: int
    sha256: str
    content_type: str = "unknown"
    added_at: str = field(default_factory=utc_now)


@dataclass
class PcbProject:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    format_version: int = PROJECT_FORMAT_VERSION
    created_at: str = field(default_factory=utc_now)
    modified_at: str = field(default_factory=utc_now)
    source_files: list[SourceFile] = field(default_factory=list)
    layers: list[dict] = field(default_factory=list)
    machining_settings: dict = field(default_factory=dict)
    machine_profile: str = "Unverified Example"
    warnings: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    def touch(self) -> None:
        self.modified_at = utc_now()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PcbProject":
        files = [SourceFile(**item) for item in data.get("source_files", [])]
        known = {
            key: value
            for key, value in data.items()
            if key in cls.__dataclass_fields__ and key != "source_files"
        }
        return cls(source_files=files, **known)


def project_directory(data_projects_dir: Path, project: PcbProject) -> Path:
    return data_projects_dir / f"{slugify(project.name)}-{project.id}"


def project_metadata_path(project_dir: Path) -> Path:
    return project_dir / "project.json"

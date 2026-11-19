"""Application composition root.

Creates shared services once and hands them to the UI. Keeping this outside
the window class makes the app testable without opening a GUI.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.event_manager import EventManager
from app.core.logging_manager import setup_logging
from app.core.project_manager import ProjectManager
from app.services.import_service import ImportService
from config.application_config import data_paths, resolve_data_dir
from config.default_settings import AppSettings, settings_path
from config.machine_profiles import MachineProfile, built_in_profiles


class Application:
    def __init__(self, data_dir: str | Path | None = None, simulation: bool = False) -> None:
        self.data_dir = resolve_data_dir(str(data_dir) if data_dir else None)
        self.paths = data_paths(self.data_dir)
        self.events = EventManager()
        self.log: logging.Logger = logging.getLogger("smartdrill")
        self.settings = AppSettings()
        self.machine_profiles: list[MachineProfile] = built_in_profiles()
        self.active_profile: MachineProfile = self.machine_profiles[0]
        self.projects = ProjectManager(self.paths["projects"], self.events)
        self.importer = ImportService(self.projects)
        self.force_simulation = simulation

    def initialize(self) -> None:
        self.log = setup_logging(self.paths["logs"])
        self._load_settings()
        self.log.info("SmartDrill Pro initialized (data dir: %s)", self.data_dir)

    def _load_settings(self) -> None:
        path = settings_path(self.data_dir)
        if not path.is_file():
            return
        try:
            self.settings = AppSettings.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.log.warning("Using default settings; could not read %s: %s", path, exc)

    @property
    def simulation_mode(self) -> bool:
        return self.force_simulation or self.settings.simulation_mode

    def save_settings(self) -> None:
        path = settings_path(self.data_dir)
        path.write_text(json.dumps(self.settings.to_dict(), indent=2), encoding="utf-8")
        self.events.emit("settings_changed", self.settings)

    def shutdown(self) -> None:
        if self.projects.active is not None:
            self.projects.save()
        self.log.info("SmartDrill Pro shut down")

"""User preferences and conservative machining limits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from config.application_config import (
    DEFAULT_BAUD_RATE,
    DEFAULT_RX_BUFFER_BYTES,
    DEFAULT_SERIAL_TIMEOUT_S,
    DEFAULT_STATUS_POLL_MS,
)


@dataclass
class AppSettings:
    units: str = "mm"
    theme: str = "dark"
    simulation_mode: bool = True
    baud_rate: int = DEFAULT_BAUD_RATE
    rx_buffer_bytes: int = DEFAULT_RX_BUFFER_BYTES
    serial_timeout_s: float = DEFAULT_SERIAL_TIMEOUT_S
    status_poll_ms: int = DEFAULT_STATUS_POLL_MS

    # Safety limits. These are starting values only and must be calibrated.
    max_cut_depth_mm: float = 2.0
    max_feed_rate_mm_min: int = 1000
    max_plunge_rate_mm_min: int = 300

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        known = {field: data[field] for field in cls.__dataclass_fields__ if field in data}
        return cls(**known)


def settings_path(data_dir: Path) -> Path:
    return data_dir / "settings.json"

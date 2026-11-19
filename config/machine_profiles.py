"""Editable machine profiles.

A machine profile is a named set of machine limits and calibration values.
The built-in profile is deliberately conservative and marked UNVERIFIED:
real steps/mm, travel, acceleration and spindle settings must be measured on
the physical machine and then edited by the user.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class MachineProfile:
    name: str
    description: str = "UNVERIFIED example profile - calibrate before use"
    calibrated: bool = False
    steps_per_mm: dict[str, float] = field(
        default_factory=lambda: {"X": 80.0, "Y": 80.0, "Z": 80.0}
    )
    max_travel_mm: dict[str, float] = field(
        default_factory=lambda: {"X": 100.0, "Y": 100.0, "Z": 30.0}
    )
    max_feed_mm_min: dict[str, float] = field(
        default_factory=lambda: {"X": 500.0, "Y": 500.0, "Z": 200.0}
    )
    max_accel_mm_s2: dict[str, float] = field(
        default_factory=lambda: {"X": 100.0, "Y": 100.0, "Z": 50.0}
    )
    homing_enabled: bool = False
    hard_limits_enabled: bool = False
    soft_limits_enabled: bool = False
    spindle_supported: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MachineProfile":
        known = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        return cls(**known)

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Machine profile needs a name.")
        for axis in ("X", "Y", "Z"):
            for label, values in (
                ("steps/mm", self.steps_per_mm),
                ("travel", self.max_travel_mm),
                ("feed", self.max_feed_mm_min),
                ("acceleration", self.max_accel_mm_s2),
            ):
                if float(values.get(axis, 0.0)) <= 0:
                    raise ValueError(f"{axis} {label} must be greater than zero.")


def example_profile() -> MachineProfile:
    return MachineProfile(name="Unverified Example")


def built_in_profiles() -> list[MachineProfile]:
    return [example_profile()]

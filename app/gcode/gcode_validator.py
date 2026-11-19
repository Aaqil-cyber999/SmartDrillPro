"""Safety checks for G-code before it can be sent to a machine."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.gcode.gcode_parser import WORD_RE, ParsedGcode
from config.default_settings import AppSettings
from config.machine_profiles import MachineProfile

SUPPORTED_G = {0, 1, 2, 3, 4, 17, 18, 19, 20, 21, 28, 90, 91, 94}
SUPPORTED_M = {0, 1, 2, 3, 4, 5, 30}


@dataclass
class ValidationIssue:
    severity: str  # error or warning
    message: str
    line: int | None = None


@dataclass
class ValidationReport:
    source: str
    issues: list[ValidationIssue] = field(default_factory=list)
    estimated_time_s: float = 0.0
    move_counts: dict[str, int] = field(default_factory=dict)
    bounds: tuple[float, float, float, float] | None = None

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def safe(self) -> bool:
        return not self.errors


def validate_gcode(
    parsed: ParsedGcode,
    settings: AppSettings | None = None,
    profile: MachineProfile | None = None,
) -> ValidationReport:
    settings = settings or AppSettings()
    profile = profile or MachineProfile(name="Unverified Example")
    report = ValidationReport(parsed.source, move_counts=parsed.counts(), bounds=parsed.bounds)

    if parsed.units != "mm":
        report.issues.append(ValidationIssue("error", "Program uses inch units; require G21 (millimetres)."))
    if not parsed.moves:
        report.issues.append(ValidationIssue("error", "Program contains no motion commands."))

    limits = profile.max_travel_mm
    travel = {"X": limits.get("X", 0.0), "Y": limits.get("Y", 0.0)}
    max_z_up = limits.get("Z", 0.0)
    min_z = -abs(settings.max_cut_depth_mm)
    max_feed_xy = min(
        settings.max_feed_rate_mm_min,
        profile.max_feed_mm_min.get("X", settings.max_feed_rate_mm_min),
    )
    max_feed_z = min(
        settings.max_plunge_rate_mm_min,
        profile.max_feed_mm_min.get("Z", settings.max_plunge_rate_mm_min),
    )

    for move in parsed.moves:
        end_x, end_y, end_z = move.end
        if travel["X"] and abs(end_x) > travel["X"]:
            report.issues.append(ValidationIssue("error", f"X {end_x:.2f} exceeds configured X travel.", move.line_number))
        if travel["Y"] and abs(end_y) > travel["Y"]:
            report.issues.append(ValidationIssue("error", f"Y {end_y:.2f} exceeds configured Y travel.", move.line_number))
        if end_z < min_z:
            report.issues.append(ValidationIssue("error", f"Z {end_z:.2f} is deeper than the {min_z:.2f} mm safety limit.", move.line_number))
        if end_z > max_z_up:
            report.issues.append(ValidationIssue("warning", f"Z {end_z:.2f} is above the configured travel limit.", move.line_number))
        if move.feed is not None:
            if move.kind in {"cut", "rapid"} and move.feed > max_feed_xy:
                report.issues.append(ValidationIssue("error", f"XY feed {move.feed:.0f} exceeds the safety limit.", move.line_number))
            if move.kind == "plunge" and move.feed > max_feed_z:
                report.issues.append(ValidationIssue("error", f"Plunge feed {move.feed:.0f} exceeds the safety limit.", move.line_number))
            if move.feed > 0:
                report.estimated_time_s += (move.length_mm / move.feed) * 60.0

    for move in parsed.moves:
        if move.raw.upper().startswith(("G2", "G02", "G3", "G03")):
            report.issues.append(ValidationIssue("warning", "Arc move preview is approximated as a straight chord.", move.line_number))

    seen_unsupported: set[str] = set()
    has_program_end = False
    for line_number, code in parsed.program_lines:
        words: dict[str, list[float]] = {}
        for letter, value in WORD_RE.findall(code):
            words.setdefault(letter.upper(), []).append(float(value))
        for letter, supported in (("G", SUPPORTED_G), ("M", SUPPORTED_M)):
            for value in words.get(letter, []):
                number = int(value)
                if number in (2, 30) and letter == "M":
                    has_program_end = True
                if number not in supported:
                    token = f"{letter}{number}"
                    if token not in seen_unsupported:
                        seen_unsupported.add(token)
                        report.issues.append(ValidationIssue(
                            "error", f"Unsupported command {token}; review the program before use.",
                            line_number,
                        ))
    if not has_program_end:
        report.issues.append(ValidationIssue("error", "Program has no M2/M30 end command."))

    report.issues.append(ValidationIssue(
        "warning", "UNVERIFIED machine profile: confirm limits, homing and spindle settings before cutting."
    ))
    return report

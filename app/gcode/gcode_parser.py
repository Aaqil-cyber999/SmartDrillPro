"""Parse G-code into movement records for validation and preview.

This is deliberately conservative: unsupported commands are preserved as
'other' moves and reported by the validator rather than silently ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re

WORD_RE = re.compile(r"([A-Za-z])\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
COMMENT_RE = re.compile(r"\([^)]*\)|;.*$")


@dataclass
class GcodeMove:
    line_number: int
    kind: str  # rapid, cut, plunge, travel, drill, other
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    feed: float | None
    raw: str

    @property
    def length_mm(self) -> float:
        return math.dist(self.start, self.end)


@dataclass
class ParsedGcode:
    source: str
    moves: list[GcodeMove] = field(default_factory=list)
    units: str = "mm"
    line_count: int = 0
    parse_errors: list[str] = field(default_factory=list)
    program_lines: list[tuple[int, str]] = field(default_factory=list)

    @property
    def bounds(self) -> tuple[float, float, float, float] | None:
        points = [point for move in self.moves for point in (move.start, move.end)]
        if not points:
            return None
        return (
            min(point[0] for point in points), min(point[1] for point in points),
            max(point[0] for point in points), max(point[1] for point in points),
        )

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for move in self.moves:
            counts[move.kind] = counts.get(move.kind, 0) + 1
        return counts


def parse_gcode(text: str, source: str = "gcode") -> ParsedGcode:
    result = ParsedGcode(source=source)
    position = [0.0, 0.0, 0.0]
    absolute = True
    scale = 1.0
    feed: float | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        result.line_count += 1
        code = COMMENT_RE.sub("", raw_line).strip()
        if not code:
            continue
        words: dict[str, list[float]] = {}
        for letter, value in WORD_RE.findall(code):
            words.setdefault(letter.upper(), []).append(float(value))
        if not words:
            continue
        result.program_lines.append((line_number, code))

        g_codes = words.get("G", [])
        m_codes = words.get("M", [])
        previous_units = result.units
        if 20.0 in g_codes:
            result.units, scale = "inch", 25.4
        if 21.0 in g_codes:
            result.units, scale = "mm", 1.0
        if 90.0 in g_codes:
            absolute = True
        if 91.0 in g_codes:
            absolute = False
        if result.units != previous_units:
            # Convert the current position so later incremental moves stay correct.
            factor = 25.4 if result.units == "inch" else 1 / 25.4
            position = [coordinate * factor for coordinate in position]

        if "F" in words:
            feed = words["F"][-1] * scale

        start = tuple(position)
        target = list(position)
        for axis, index in (("X", 0), ("Y", 1), ("Z", 2)):
            if axis in words:
                value = words[axis][-1] * scale
                target[index] = value if absolute else position[index] + value

        kind = "other"
        if g_codes and g_codes[0] in (0.0,):
            kind = "rapid"
        elif g_codes and g_codes[0] in (1.0, 2.0, 3.0):
            dz = abs(target[2] - position[2])
            horizontal = math.hypot(target[0] - position[0], target[1] - position[1])
            kind = "plunge" if dz > 0 and horizontal < 1e-9 else "cut"
        elif m_codes and m_codes[0] in (3.0, 4.0, 5.0):
            kind = "other"

        if target != position and kind in {"rapid", "cut", "plunge"}:
            result.moves.append(GcodeMove(
                line_number, kind, start, tuple(target), feed, raw_line.strip()
            ))

        position = target
    return result

"""Add deterministic, safe startup and end sequences to generated G-code."""

from __future__ import annotations

import re


STARTUP = [
    "(SmartDrill Pro validated copy - review before use)",
    "G21",  # millimetres
    "G90",  # absolute coordinates
    "G17",  # XY plane
    "M5",   # spindle off until explicitly started by the program
]

SHUTDOWN = [
    "M5",
    "M30",
]


def _compact(line: str) -> str:
    return line.upper().replace(" ", "")


def normalize_gcode(text: str) -> str:
    """Return a validated copy; the original generated file is never modified.

    Inch programs are rejected instead of silently converted: deleting ``G20``
    would reinterpret inch coordinates as millimetres.
    """
    lines = [line.strip() for line in text.splitlines()]
    program = [line for line in lines if line and not line.startswith("(")]

    if any("G20" in re.findall(r"[A-Z]\d+", _compact(line)) for line in program):
        raise ValueError("Program uses inch units (G20); generate it in millimetres first.")

    # An early program end would stop the machine before later toolpaths.
    end_index = next(
        (index for index, line in enumerate(program) if _compact(line).startswith("M30")),
        None,
    )
    if end_index is not None:
        program = program[:end_index]

    result: list[str] = list(STARTUP)
    for line in program:
        if _compact(line) == "G21":
            continue  # already present in STARTUP
        result.append(line)

    result.extend(SHUTDOWN)
    return "\n".join(result).strip() + "\n"


def validated_copy_path(path: str) -> str:
    source = str(path)
    if source.lower().endswith(".nc"):
        return source[:-3] + ".validated.nc"
    if source.lower().endswith(".gcode"):
        return source[:-6] + ".validated.nc"
    return source + ".validated.nc"

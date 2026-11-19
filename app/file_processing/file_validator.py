"""Content-based validation for PCB manufacturing files.

File extensions alone are not trustworthy: KiCad, Altium, Eagle, DipTrace and
EasyEDA all export different suffixes. We sniff file content first, then use
the extension only as a tie-breaker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import zipfile

GERBER_SUFFIXES = {
    ".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo",
    ".gtp", ".gbp", ".gm1", ".gko", ".gml", ".art", ".pho",
}
EXCELLON_SUFFIXES = {".drl", ".xln", ".drd", ".ncd", ".tap"}
TEXT_SUFFIXES = {".txt", ".log", ".par", ".ncparam"}
SUPPORTED_SUFFIXES = GERBER_SUFFIXES | EXCELLON_SUFFIXES | TEXT_SUFFIXES | {".zip"}


@dataclass
class ValidationResult:
    content_type: str  # gerber, excellon, zip, unknown
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def read_preview(path: Path, limit: int = 64 * 1024) -> str:
    data = path.read_bytes()[:limit]
    return data.decode("ascii", errors="ignore").upper()


def is_zip_file(path: Path) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def validate_text(text: str, suffix: str = "") -> ValidationResult:
    """Validate a decoded manufacturing file body."""
    errors: list[str] = []
    warnings: list[str] = []

    has_gerber_format = "%FS" in text
    has_gerber_end = "M02" in text or "M2*" in text
    has_gerber_codes = "D01" in text or "D02" in text or "D03" in text or "ADD" in text
    gerber_score = sum((has_gerber_format, has_gerber_end, has_gerber_codes))

    has_excellon_header = "M48" in text
    has_excellon_end = "M30" in text or "M00" in text
    has_excellon_tool = "T0" in text or "T1" in text or "%" in text
    excellon_score = sum((has_excellon_header, has_excellon_end, has_excellon_tool))

    if gerber_score >= 2 and gerber_score >= excellon_score:
        if not has_gerber_format:
            warnings.append("Gerber format specification (%FS) not found; parsing may be unreliable.")
        if not has_gerber_end:
            warnings.append("No M02 end-of-file marker found.")
        return ValidationResult("gerber", True, errors, warnings)

    if excellon_score >= 2 and excellon_score >= gerber_score:
        if "FILE_FORMAT" not in text and "." not in text[:512]:
            warnings.append("Excellon number format is not declared; coordinates may be misinterpreted.")
        if not has_excellon_end:
            warnings.append("No M30 end-of-file marker found.")
        return ValidationResult("excellon", True, errors, warnings)

    if suffix.lower() in TEXT_SUFFIXES:
        return ValidationResult("unknown", False, ["Auxiliary text file; not a Gerber or Excellon file."], warnings)

    errors.append("Content does not look like Gerber (RS-274X) or Excellon drill data.")
    return ValidationResult("unknown", False, errors, warnings)


def validate_file(path: Path) -> ValidationResult:
    """Validate a single file on disk."""
    if not path.is_file():
        return ValidationResult("unknown", False, [f"Not a file: {path.name}"])
    try:
        if is_zip_file(path):
            return ValidationResult("zip", True)
        preview = read_preview(path)
    except OSError as exc:
        return ValidationResult("unknown", False, [f"Cannot read {path.name}: {exc}"])

    if not preview.strip():
        return ValidationResult("unknown", False, [f"{path.name} is empty."])

    result = validate_text(preview, path.suffix)
    if result.content_type == "unknown" and path.suffix.lower() in GERBER_SUFFIXES:
        # A few valid Gerbers omit the usual markers but still use '*' terminators.
        if preview.count("*") > 5:
            result = ValidationResult("gerber", True, result.errors, result.warnings + [
                "Gerber detected from command terminators; format markers are unusual."
            ])
    return result

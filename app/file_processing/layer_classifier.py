"""Guess a manufacturing layer role from filename and content hints."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.file_processing.file_validator import ValidationResult

LAYER_ROLES = (
    "top_copper",
    "bottom_copper",
    "inner_copper",
    "top_solder_mask",
    "bottom_solder_mask",
    "top_silkscreen",
    "bottom_silkscreen",
    "top_paste",
    "bottom_paste",
    "outline",
    "plated_drill",
    "nonplated_drill",
    "drill",
    "other",
)

# (compiled pattern, role, confidence). First match wins; order matters.
RULES: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"(edge[_ .-]?cuts|outline|board[_ .-]?profile|profile| mechanical|\.gm[0-9]+$|\.gko$|\.gml$)", re.I), "outline", 0.93),
    (re.compile(r"(npth|non[_ .-]?plated|unplated)", re.I), "nonplated_drill", 0.96),
    (re.compile(r"(pth|plated)", re.I), "plated_drill", 0.95),
    (re.compile(r"(\.drl$|\.xln$|\.drd$|\.ncd$|\.tap$|drill)", re.I), "drill", 0.88),
    (re.compile(r"(f[_ .-]?cu|front[_ .-]?copper|top[_ .-]?copper|\.gtl$|copper[_ .-]?top|top\.gbr)", re.I), "top_copper", 0.94),
    (re.compile(r"(b[_ .-]?cu|back[_ .-]?copper|bottom[_ .-]?copper|\.gbl$|copper[_ .-]?bottom|bottom\.gbr)", re.I), "bottom_copper", 0.94),
    (re.compile(r"(in[1-9n][_ .-]?cu|inner[_ .-]?copper|\.g[2-9][lrp]$|layer[_ ]?[2-9])", re.I), "inner_copper", 0.86),
    (re.compile(r"(f[_ .-]?(mask|resist)|top[_ .-]?(mask|solder)|\.gts$)", re.I), "top_solder_mask", 0.92),
    (re.compile(r"(b[_ .-]?(mask|resist)|bottom[_ .-]?(mask|solder)|\.gbs$)", re.I), "bottom_solder_mask", 0.92),
    (re.compile(r"(f[_ .-]?(silk|silkscreen)|top[_ .-]?silk|\.gto$)", re.I), "top_silkscreen", 0.91),
    (re.compile(r"(b[_ .-]?(silk|silkscreen)|bottom[_ .-]?silk|\.gbo$)", re.I), "bottom_silkscreen", 0.91),
    (re.compile(r"(f[_ .-]?paste|top[_ .-]?paste|\.gtp$)", re.I), "top_paste", 0.90),
    (re.compile(r"(b[_ .-]?paste|bottom[_ .-]?paste|\.gbp$)", re.I), "bottom_paste", 0.90),
]


@dataclass
class LayerClassification:
    role: str
    confidence: float
    reason: str


def classify_layer(name: str, validation: ValidationResult | None = None) -> LayerClassification:
    """Classify a file name. A drill file always wins over Gerber filename hints."""
    if validation is not None and validation.content_type == "excellon":
        for pattern, role, confidence in RULES:
            if role in {"nonplated_drill", "plated_drill", "drill"} and pattern.search(name):
                return LayerClassification(role, confidence, "Excellon content and drill filename hint")
        return LayerClassification("drill", 0.80, "Excellon content; plating unknown")

    for pattern, role, confidence in RULES:
        if pattern.search(name):
            return LayerClassification(role, confidence, "filename pattern")

    if validation is not None and validation.content_type == "gerber":
        return LayerClassification("other", 0.35, "Gerber content; role not recognized")
    return LayerClassification("other", 0.10, "no matching rule")

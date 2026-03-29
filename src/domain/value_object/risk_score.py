"""Value object: risk breakdown for a proposed PR."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskScore:
    """Immutable risk assessment with component breakdown."""

    value: float
    line_risk: float = 0.0
    complexity_risk: float = 0.0
    dep_risk: float = 0.0
    diversity_risk: float = 0.0

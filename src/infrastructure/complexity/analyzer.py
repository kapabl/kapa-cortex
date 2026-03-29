"""Complexity analysis via lizard."""

from __future__ import annotations

from src.domain.value_object.file_complexity import FileComplexity
from src.domain.port.complexity_analyzer import ComplexityAnalyzer
from src.infrastructure.complexity.lizard_analyzer import analyze_lizard


class LizardAnalyzer(ComplexityAnalyzer):
    """Uses lizard for function-level complexity metrics."""

    def analyze(self, file_paths: list[str]) -> dict[str, FileComplexity]:
        return analyze_lizard(file_paths)

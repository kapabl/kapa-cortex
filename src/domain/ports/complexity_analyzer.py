"""Port: code complexity analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.file_complexity import FileComplexity


class ComplexityAnalyzer(ABC):
    """Contract for complexity analysis. Implemented by infrastructure."""

    @abstractmethod
    def analyze(self, file_paths: list[str]) -> dict[str, FileComplexity]: ...

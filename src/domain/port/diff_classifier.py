"""Port: classify diffs as structural vs cosmetic."""

from __future__ import annotations

from abc import ABC, abstractmethod


class DiffClassifier(ABC):
    """Contract for classifying code changes."""

    @abstractmethod
    def structural_ratio(self, file_path: str, diff_text: str) -> float:
        """Return 0.0-1.0: fraction of changes that are structural (not cosmetic)."""
        ...

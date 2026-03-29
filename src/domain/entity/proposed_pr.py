"""Entity: a proposed pull request grouping changed files."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.entity.changed_file import ChangedFile


@dataclass
class ProposedPR:
    """A group of ChangedFiles proposed as one reviewable PR."""

    index: int
    title: str
    files: list[ChangedFile] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    merge_strategy: str = "squash"
    description: str = ""
    risk_score: float = 0.0

    @property
    def total_code_lines(self) -> int:
        return sum(
            file.code_lines for file in self.files
            if not file.is_text_or_docs
        )

    @property
    def total_all_lines(self) -> int:
        return sum(file.code_lines for file in self.files)

    @property
    def total_complexity(self) -> int:
        return sum(file.cyclomatic_complexity for file in self.files)

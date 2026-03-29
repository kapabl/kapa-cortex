"""Entity: a file that changed on the branch."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.domain.entity.symbol_ref import SymbolRef

_TEXT_EXTENSIONS = frozenset({
    ".md", ".txt", ".rst", ".adoc", ".csv", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".lock", ".log",
})


@dataclass
class ChangedFile:
    """A file modified between the feature branch and the base."""

    path: str
    added: int
    removed: int
    status: str              # A/M/D/R
    diff_text: str = ""
    complexity: object = None       # FileComplexity, set by enrichment
    symbols_defined: list = field(default_factory=list)
    symbols_used: list[SymbolRef] = field(default_factory=list)
    structural_ratio: float = 1.0  # 0-1: fraction of structural (non-cosmetic) changes

    @property
    def is_text_or_docs(self) -> bool:
        return Path(self.path).suffix.lower() in _TEXT_EXTENSIONS

    @property
    def code_lines(self) -> int:
        return self.added + self.removed

    @property
    def module_key(self) -> str:
        parts = Path(self.path).parts
        return "__root__" if len(parts) == 1 else parts[0]

    @property
    def ext(self) -> str:
        return Path(self.path).suffix.lower()

    @property
    def cyclomatic_complexity(self) -> int:
        if self.complexity and hasattr(self.complexity, "complexity"):
            return self.complexity.complexity
        return 0

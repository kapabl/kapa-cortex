"""Value object: a symbol defined in a source file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolDef:
    """Immutable symbol definition extracted from source."""

    name: str
    kind: str         # "function", "class", "struct", "variable", etc.
    line: int = 0
    scope: str = ""

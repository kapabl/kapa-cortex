"""Value object: a reference to a symbol used in source code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolRef:
    """Immutable reference to a symbol used (not defined) in source."""

    name: str
    kind: str = ""       # "call", "type_annotation", "base_class", etc.
    line: int = 0

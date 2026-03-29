"""Value object: an import/dependency reference from source code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportRef:
    """Immutable import reference extracted from source."""

    raw: str
    module: str
    kind: str = ""    # "module", "header", "package", "target", etc.

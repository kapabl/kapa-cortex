"""Value object: a single file matching criterion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionRule:
    """Immutable rule for matching files to an extraction prompt."""

    kind: str           # "glob", "regex", "path_prefix", "keyword", "ext", "lang"
    pattern: str
    description: str = ""

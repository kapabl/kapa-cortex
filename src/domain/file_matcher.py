"""Domain service: match files against extraction rules."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from src.domain.changed_file import ChangedFile
from src.domain.extraction_rule import ExtractionRule


def match_files(
    files: list[ChangedFile],
    rules: list[ExtractionRule],
) -> list[ChangedFile]:
    """Return files that match at least one rule."""
    return [f for f in files if _matches_any(f, rules)]


def _matches_any(f: ChangedFile, rules: list[ExtractionRule]) -> bool:
    return any(_matches(f, r) for r in rules)


def _matches(f: ChangedFile, rule: ExtractionRule) -> bool:
    if rule.kind == "glob":
        return (
            fnmatch.fnmatch(f.path, rule.pattern)
            or fnmatch.fnmatch(Path(f.path).name, rule.pattern)
        )
    if rule.kind == "path_prefix":
        return f.path.startswith(rule.pattern)
    if rule.kind == "ext":
        return Path(f.path).suffix.lower() == rule.pattern
    if rule.kind == "regex":
        return bool(re.search(rule.pattern, f.path))
    if rule.kind == "keyword":
        kw = rule.pattern.lower()
        return kw in f.path.lower() or kw in f.diff_text.lower()
    return False

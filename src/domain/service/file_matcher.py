"""Domain service: match files against extraction rules."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from src.domain.entity.changed_file import ChangedFile
from src.domain.value_object.extraction_rule import ExtractionRule


def match_files(
    files: list[ChangedFile],
    rules: list[ExtractionRule],
) -> list[ChangedFile]:
    """Return files that match at least one rule."""
    return [file for file in files if _matches_any(file, rules)]


def _matches_any(file: ChangedFile, rules: list[ExtractionRule]) -> bool:
    return any(_matches(file, r) for r in rules)


def _matches(file: ChangedFile, rule: ExtractionRule) -> bool:
    if rule.kind == "glob":
        return (
            fnmatch.fnmatch(file.path, rule.pattern)
            or fnmatch.fnmatch(Path(file.path).name, rule.pattern)
        )
    if rule.kind == "path_prefix":
        return file.path.startswith(rule.pattern)
    if rule.kind == "ext":
        return Path(file.path).suffix.lower() == rule.pattern
    if rule.kind == "regex":
        return bool(re.search(rule.pattern, file.path))
    if rule.kind == "keyword":
        kw = rule.pattern.lower()
        return kw in file.path.lower() or kw in file.diff_text.lower()
    return False

"""Domain service: match test files with their implementations."""

from __future__ import annotations

import re

from src.domain.entity.changed_file import ChangedFile
from src.domain.value_object.test_pair import TestPair

_PATTERNS = [
    (re.compile(r"^(.*/)?test_(.+)\.py$"), r"\1\2.py"),
    (re.compile(r"^(.*/)?(.+)_test\.py$"), r"\1\2.py"),
    (re.compile(r"^(.*/)?(.+)_test\.go$"), r"\1\2.go"),
    (re.compile(r"^(.*/)?(.+)\.(test|spec)\.(tsx?|jsx?)$"), r"\1\2.\4"),
    (re.compile(r"^(.*/)?(.+)Test\.(java|kt|kts)$"), r"\1\2.\3"),
    (re.compile(r"^(.*/)?(.+)_test\.(cpp|cc|cxx)$"), r"\1\2.\3"),
    (re.compile(r"^(.*/)?test_(.+)\.(cpp|cc|cxx)$"), r"\1\2.\3"),
    (re.compile(r"^(.*/)tests/(.+)\.rs$"), r"\1src/\2.rs"),
    (re.compile(r"^(.*/)?__tests__/(.+)\.(tsx?|jsx?)$"), r"\1\2.\3"),
]


def find_test_pairs(files: list[ChangedFile]) -> list[TestPair]:
    """Find test-implementation pairs among changed files."""
    all_paths = {file.path for file in files}
    pairs: list[TestPair] = []

    for file in files:
        for pattern, replacement in _PATTERNS:
            if pattern.match(file.path):
                impl = pattern.sub(replacement, file.path)
                if impl in all_paths and impl != file.path:
                    pairs.append(TestPair(file.path, impl))
                break

    return pairs

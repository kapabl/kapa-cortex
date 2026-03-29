"""Domain service: match test files with their implementations."""

from __future__ import annotations

import re

from src.domain.changed_file import ChangedFile
from src.domain.test_pair import TestPair

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
    all_paths = {f.path for f in files}
    pairs: list[TestPair] = []

    for f in files:
        for pattern, replacement in _PATTERNS:
            if pattern.match(f.path):
                impl = pattern.sub(replacement, f.path)
                if impl in all_paths and impl != f.path:
                    pairs.append(TestPair(f.path, impl))
                break

    return pairs

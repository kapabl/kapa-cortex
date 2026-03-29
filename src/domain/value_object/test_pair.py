"""Value object: test file paired with its implementation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestPair:
    """Immutable pairing of a test file with its implementation."""

    test_path: str
    impl_path: str

"""Value object: merge strategy enum."""

from __future__ import annotations

from enum import Enum


class MergeStrategy(str, Enum):
    SQUASH = "squash"
    MERGE = "merge"
    REBASE = "rebase"

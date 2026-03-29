"""Domain events — things that happened during analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyCycleDetected:
    """A dependency cycle was found and broken."""
    files: list[str]


@dataclass(frozen=True)
class DependencyPulledIn:
    """A file was pulled into extraction because it's a dependency."""
    file_path: str
    depended_on_by: str


@dataclass(frozen=True)
class StepFailed:
    """A plan execution step failed."""
    step_id: int
    error: str
    command: str

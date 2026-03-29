"""Value objects: complexity metrics for files and functions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FunctionComplexity:
    """Per-function complexity metrics."""

    name: str
    start_line: int
    end_line: int
    cyclomatic: int
    cognitive: int = 0
    token_count: int = 0
    parameter_count: int = 0
    length: int = 0


@dataclass
class FileComplexity:
    """Aggregate complexity metrics for a single file."""

    language: str
    lines: int
    code: int
    comments: int
    blanks: int
    complexity: int
    functions: list[FunctionComplexity] = field(default_factory=list)
    avg_cyclomatic: float = 0.0
    max_cyclomatic: int = 0

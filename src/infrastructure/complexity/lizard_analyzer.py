"""Run lizard for function-level cyclomatic complexity."""

from __future__ import annotations

import os

import lizard

from src.domain.value_object.file_complexity import FileComplexity, FunctionComplexity


def analyze_lizard(file_paths: list[str]) -> dict[str, FileComplexity]:
    """Run lizard on files for per-function complexity metrics."""
    metrics: dict[str, FileComplexity] = {}
    for path in file_paths:
        if not os.path.exists(path):
            continue
        result = _analyze_single(path)
        if result:
            metrics[path] = result
    return metrics


def _analyze_single(path: str) -> FileComplexity | None:
    try:
        analysis = lizard.analyze_file(path)  # type: ignore[attr-defined]
    except Exception:
        return None

    functions = _extract_functions(analysis)
    total_cyclomatic = sum(func.cyclomatic for func in functions)
    avg_cyclomatic = total_cyclomatic / len(functions) if functions else 0
    max_cyclomatic = max((func.cyclomatic for func in functions), default=0)

    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    return FileComplexity(
        language=ext, lines=analysis.nloc, code=analysis.nloc,
        comments=0, blanks=0, complexity=total_cyclomatic,
        functions=functions,
        avg_cyclomatic=round(avg_cyclomatic, 1),
        max_cyclomatic=max_cyclomatic,
    )


def _extract_functions(analysis) -> list[FunctionComplexity]:
    return [
        FunctionComplexity(
            name=func.name,
            start_line=func.start_line,
            end_line=func.end_line,
            cyclomatic=func.cyclomatic_complexity,
            token_count=func.token_count,
            parameter_count=len(func.parameters),
            length=func.nloc,
        )
        for func in analysis.function_list
    ]

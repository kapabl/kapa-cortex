"""Infrastructure: complexity analysis via lizard/scc."""

from __future__ import annotations

from src.domain.file_complexity import FileComplexity
from src.domain.ports.complexity_analyzer import ComplexityAnalyzer
from lang_parsers import analyze_complexity_best as _analyze


class LizardSccAnalyzer(ComplexityAnalyzer):
    """Uses lizard (preferred) or scc for complexity metrics."""

    def analyze(self, file_paths: list[str]) -> dict[str, FileComplexity]:
        raw = _analyze(file_paths)
        result: dict[str, FileComplexity] = {}
        for path, metrics in raw.items():
            result[path] = FileComplexity(
                language=metrics.language,
                lines=metrics.lines,
                code=metrics.code,
                comments=metrics.comments,
                blanks=metrics.blanks,
                complexity=metrics.complexity,
                avg_cyclomatic=metrics.avg_cyclomatic,
                max_cyclomatic=metrics.max_cyclomatic,
            )
        return result

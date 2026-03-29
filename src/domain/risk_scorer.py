"""Domain service: compute risk scores for proposed PRs."""

from __future__ import annotations

from src.domain.proposed_pr import ProposedPR


def compute_risk(pr: ProposedPR) -> float:
    """
    Compute a 0.0-1.0 risk score from:
      - code line count
      - cyclomatic complexity
      - cross-PR dependency count
      - file type diversity
    """
    line_risk = min(pr.total_code_lines / 500.0, 1.0)
    complexity_risk = min(pr.total_complexity / 50.0, 1.0)
    dep_risk = min(len(pr.depends_on) / 5.0, 1.0)

    ext_diversity = len({
        f.ext for f in pr.files if not f.is_text_or_docs
    })
    diversity_risk = min(ext_diversity / 4.0, 1.0)

    return round(
        0.3 * line_risk
        + 0.3 * complexity_risk
        + 0.2 * dep_risk
        + 0.2 * diversity_risk,
        2,
    )

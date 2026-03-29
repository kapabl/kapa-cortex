"""Domain service: assign merge strategies to PRs."""

from __future__ import annotations

from src.domain.merge_strategy import MergeStrategy
from src.domain.proposed_pr import ProposedPR


def assign_strategies(prs: list[ProposedPR]) -> None:
    """
    Assign merge strategy per PR:
      - merge  : has dependents, or high risk (preserve bisect context)
      - rebase : docs/config only, no dependents (linear history)
      - squash : default (clean single commit)
    """
    depended_on = _find_depended_on(prs)

    for pr in prs:
        all_docs = all(f.is_text_or_docs for f in pr.files)
        has_dependents = pr.index in depended_on

        if has_dependents:
            _set_merge(pr)
        elif all_docs:
            _set_rebase(pr)
        elif pr.risk_score > 0.6:
            _set_merge_high_risk(pr)
        else:
            _set_squash(pr)


def _find_depended_on(prs: list[ProposedPR]) -> set[int]:
    result: set[int] = set()
    for pr in prs:
        result.update(pr.depends_on)
    return result


def _set_merge(pr: ProposedPR) -> None:
    pr.merge_strategy = MergeStrategy.MERGE
    pr.description = (
        "Use **merge commit** — later PRs depend on this one, "
        "preserving the merge point simplifies rebasing."
    )


def _set_rebase(pr: ProposedPR) -> None:
    pr.merge_strategy = MergeStrategy.REBASE
    pr.description = "Use **rebase** — docs/config only, linear history."


def _set_merge_high_risk(pr: ProposedPR) -> None:
    pr.merge_strategy = MergeStrategy.MERGE
    pr.description = (
        "Use **merge commit** — high complexity, "
        "preserves full context for bisect/revert."
    )


def _set_squash(pr: ProposedPR) -> None:
    pr.merge_strategy = MergeStrategy.SQUASH
    pr.description = "Use **squash merge** — clean single commit on main."

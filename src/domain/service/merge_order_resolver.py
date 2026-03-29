"""Domain service: compute merge order and parallelism waves."""

from __future__ import annotations

from src.domain.entity.proposed_pr import ProposedPR


def compute_merge_order(prs: list[ProposedPR]) -> list[ProposedPR]:
    """Return PRs in dependency-safe merge order."""
    merged: set[int] = set()
    result: list[ProposedPR] = []
    remaining = list(prs)

    while remaining:
        ready = [
            pr for pr in remaining
            if all(d in merged for d in pr.depends_on)
        ]
        if not ready:
            result.extend(remaining)
            break
        ready.sort(key=lambda pr: -pr.risk_score)
        for pr in ready:
            result.append(pr)
            merged.add(pr.index)
            remaining.remove(pr)

    return result


def compute_waves(prs: list[ProposedPR]) -> list[list[ProposedPR]]:
    """Group PRs into parallelism waves."""
    merged: set[int] = set()
    remaining = list(prs)
    waves: list[list[ProposedPR]] = []

    while remaining:
        ready = [
            pr for pr in remaining
            if all(d in merged for d in pr.depends_on)
        ]
        if not ready:
            waves.append(remaining[:])
            break
        waves.append(ready)
        for pr in ready:
            merged.add(pr.index)
            remaining.remove(pr)

    return waves


def compute_pr_dependencies(
    prs: list[ProposedPR],
    file_edges: list[tuple[str, str]],
) -> None:
    """Set depends_on for each PR based on file-level edges."""
    file_to_pr: dict[str, int] = {}
    for pr in prs:
        for f in pr.files:
            file_to_pr[f.path] = pr.index

    for pr in prs:
        dep_prs: set[int] = set()
        for f in pr.files:
            for src, tgt in file_edges:
                if src == f.path:
                    dep_idx = file_to_pr.get(tgt)
                    if dep_idx and dep_idx != pr.index:
                        dep_prs.add(dep_idx)
        pr.depends_on = sorted(dep_prs)

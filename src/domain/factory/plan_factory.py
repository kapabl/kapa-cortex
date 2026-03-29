"""Factory: builds ExecutionPlan from a StackedPRSet."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from src.domain.entity.execution_plan import ExecutionPlan, PRPlan, PlanStep
from src.domain.entity.proposed_pr import ProposedPR


def create_plan(
    prs: list[ProposedPR],
    source_branch: str,
    base_branch: str,
    remote: str = "origin",
    create_github_prs: bool = True,
) -> ExecutionPlan:
    """Build an execution plan from proposed PRs."""
    plan = ExecutionPlan(
        created_at=datetime.now(timezone.utc).isoformat(),
        source_branch=source_branch,
        base_branch=base_branch,
        total_prs=len(prs),
    )

    branch_names = _branch_names(prs, base_branch)
    ordered = _merge_order(prs)

    step_id = 0
    for pr in ordered:
        branch = branch_names[pr.index]
        pr_base = _pr_base(pr, branch_names, base_branch)

        plan.prs.append(PRPlan(
            index=pr.index, title=pr.title,
            branch_name=branch, base_branch=pr_base,
            files=[f.path for f in pr.files],
            depends_on=pr.depends_on,
            merge_strategy=pr.merge_strategy,
            code_lines=pr.total_code_lines,
            risk_score=pr.risk_score,
        ))

        step_id = _add_steps(
            plan, pr, branch, pr_base,
            source_branch, remote, create_github_prs, step_id,
        )

    step_id += 1
    plan.steps.append(PlanStep(
        id=step_id, pr_index=0, phase="cleanup",
        description=f"Return to '{source_branch}'",
        commands=[f"git checkout {source_branch}"],
    ))

    plan.mermaid = _mermaid(plan)
    return plan


def _branch_names(prs, base):
    result = {}
    for pr in prs:
        slug = re.sub(r"[^a-z0-9]+", "-", pr.title.lower())[:40].strip("-")
        result[pr.index] = f"stack/{base}/{pr.index:02d}-{slug}"
    return result


def _merge_order(prs):
    merged, result, remaining = set(), [], list(prs)
    while remaining:
        ready = [p for p in remaining if all(d in merged for d in p.depends_on)]
        if not ready:
            result.extend(remaining)
            break
        for p in ready:
            result.append(p)
            merged.add(p.index)
            remaining.remove(p)
    return result


def _pr_base(pr, branch_names, base_branch):
    if pr.depends_on:
        return branch_names[max(pr.depends_on)]
    return base_branch


def _add_steps(plan, pr, branch, pr_base, source, remote, create_prs, step_id):
    step_id += 1
    plan.steps.append(PlanStep(
        id=step_id, pr_index=pr.index, phase="branch",
        description=f"Create branch '{branch}'",
        commands=[f"git checkout -b {branch} {pr_base}"],
    ))

    step_id += 1
    checkout = [f.path for f in pr.files if f.status != "D"]
    deleted = [f.path for f in pr.files if f.status == "D"]
    cmds = []
    for i in range(0, len(checkout), 20):
        batch = checkout[i:i + 20]
        args = " ".join(f'"{f}"' for f in batch)
        cmds.append(f"git checkout {source} -- {args}")
    if deleted:
        args = " ".join(f'"{f}"' for f in deleted)
        cmds.append(f"git rm {args}")
    plan.steps.append(PlanStep(
        id=step_id, pr_index=pr.index, phase="checkout",
        description=f"Checkout {len(pr.files)} file(s)",
        commands=cmds,
    ))

    step_id += 1
    plan.steps.append(PlanStep(
        id=step_id, pr_index=pr.index, phase="commit",
        description=f"Commit: {pr.title}",
        commands=["git add -A", f"git commit -m '{pr.title}'"],
    ))

    step_id += 1
    plan.steps.append(PlanStep(
        id=step_id, pr_index=pr.index, phase="push",
        description=f"Push '{branch}'",
        commands=[f"git push -u {remote} {branch}"],
    ))

    if create_prs:
        step_id += 1
        plan.steps.append(PlanStep(
            id=step_id, pr_index=pr.index, phase="pr",
            description=f"Create GitHub PR: {pr.title}",
            commands=[
                f"gh pr create --base {pr_base} --head {branch} "
                f"--title '{pr.title}' --body 'Part of stacked PR set'"
            ],
        ))

    return step_id


def _mermaid(plan):
    colors = {"squash": "fill:#4CAF50,color:#fff", "merge": "fill:#FF9800,color:#fff", "rebase": "fill:#2196F3,color:#fff"}
    lines = ["```mermaid", "graph BT", f'  base["{plan.base_branch}"]', "  style base fill:#666,color:#fff"]
    for pr in plan.prs:
        nid = f"pr{pr.index}"
        label = f"{pr.title}\\n{len(pr.files)} files, {pr.code_lines} lines"
        lines.append(f'  {nid}["{label}"]')
        lines.append(f"  style {nid} {colors.get(pr.merge_strategy, 'fill:#999,color:#fff')}")
        for dep in pr.depends_on:
            lines.append(f"  {nid} --> pr{dep}")
        if not pr.depends_on:
            lines.append(f"  {nid} --> base")
    lines.append("```")
    return "\n".join(lines)

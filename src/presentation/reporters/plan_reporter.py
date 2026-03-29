"""Presentation: plan status and command reporters."""

from __future__ import annotations

from src.domain.execution_plan import ExecutionPlan
from src.domain.step_status import StepStatus

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
DIM = "\033[2m"


def print_plan_status(plan: ExecutionPlan) -> None:
    completed = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
    total = len(plan.steps)
    pct = int(completed / total * 100) if total else 0
    filled = int(30 * completed / total) if total else 0
    bar = f"[{'█' * filled}{'░' * (30 - filled)}]"

    print(f"\n{BOLD}  Plan Status{RESET}")
    print(f"  {bar} {pct}%")
    print(f"  {GREEN}Done: {completed}{RESET} / {total}")

    for step in plan.steps:
        icon = {
            StepStatus.COMPLETED: f"{GREEN}✓{RESET}",
            StepStatus.PENDING: f"{DIM}○{RESET}",
            StepStatus.FAILED: f"{RED}✗{RESET}",
            StepStatus.SKIPPED: f"{DIM}⊘{RESET}",
        }.get(step.status, "?")
        print(f"    {icon} Step {step.id}: {step.description}")

    nxt = next((s for s in plan.steps if s.status in (StepStatus.PENDING, StepStatus.FAILED)), None)
    if nxt:
        print(f"\n  Next: Step {nxt.id} — {nxt.description}")
    else:
        print(f"\n  {GREEN}All steps completed!{RESET}")
    print()


def print_commands(plan: ExecutionPlan) -> None:
    print(f"\n{BOLD}  Git Commands{RESET}")
    for step in plan.steps:
        for cmd in step.commands:
            print(f"  {cmd}")
    print()


def generate_shell_script(plan: ExecutionPlan) -> str:
    lines = [
        "#!/usr/bin/env bash",
        f"# Stacked PR creation — {plan.total_prs} PRs",
        f"# Source: {plan.source_branch} → {plan.base_branch}",
        "", "set -euo pipefail", "",
    ]
    for step in plan.steps:
        lines.append(f"# Step {step.id}: {step.description}")
        lines.extend(step.commands)
        lines.append("")
    lines.append(f'echo "Done! {plan.total_prs} PR branches created."')
    return "\n".join(lines)

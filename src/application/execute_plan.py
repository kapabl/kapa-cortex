"""Use case: execute a saved plan step by step."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.domain.execution_plan import ExecutionPlan
from src.domain.step_status import StepStatus
from src.domain.ports.command_runner import CommandRunner
from src.domain.ports.plan_persistence import PlanPersistence


class ExecutePlanUseCase:
    """Runs plan steps via the command runner."""

    def __init__(self, runner: CommandRunner, store: PlanPersistence):
        self._runner = runner
        self._store = store

    def execute(
        self,
        plan: ExecutionPlan,
        step_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> bool:
        steps = self._select_steps(plan, step_id)
        if not steps:
            return True

        for step in steps:
            step.status = StepStatus.IN_PROGRESS
            self._store.save(plan)

            ok = self._run_step(step, dry_run)

            step.executed_at = datetime.now(timezone.utc).isoformat()
            step.status = StepStatus.COMPLETED if ok else StepStatus.FAILED
            self._store.save(plan)

            if not ok:
                return False

        return True

    def _select_steps(self, plan, step_id):
        if step_id is not None:
            step = next((s for s in plan.steps if s.id == step_id), None)
            if not step or step.status == StepStatus.COMPLETED:
                return []
            return [step]
        return [
            s for s in plan.steps
            if s.status in (StepStatus.PENDING, StepStatus.FAILED)
        ]

    def _run_step(self, step, dry_run):
        outputs = []
        for cmd in step.commands:
            ok, output = self._runner.run(cmd, dry_run=dry_run)
            outputs.append(output)
            if not ok:
                step.error = output
                step.output = "\n".join(outputs)
                return False
        step.output = "\n".join(outputs)
        return True

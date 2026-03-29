"""Infrastructure: JSON file persistence for execution plans."""

from __future__ import annotations

import json
from pathlib import Path

from src.domain.execution_plan import ExecutionPlan
from src.domain.ports.plan_persistence import PlanPersistence

DEFAULT_PLAN_FILE = ".stacked-pr-plan.json"


class JsonPlanStore(PlanPersistence):
    """Saves/loads execution plans as JSON files."""

    def __init__(self, path: str = DEFAULT_PLAN_FILE):
        self._path = path

    def save(self, plan: ExecutionPlan) -> None:
        Path(self._path).write_text(
            json.dumps(plan.to_dict(), indent=2) + "\n"
        )

    def load(self) -> ExecutionPlan:
        if not Path(self._path).exists():
            raise FileNotFoundError(
                f"No plan at {self._path}. Run the analyzer first."
            )
        data = json.loads(Path(self._path).read_text())
        return ExecutionPlan.from_dict(data)

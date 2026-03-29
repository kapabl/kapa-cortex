"""Tests for execution plan serialization."""

import json
import unittest
from src.domain.entity.execution_plan import ExecutionPlan, PRPlan, PlanStep


class TestExecutionPlan(unittest.TestCase):
    def test_round_trip(self):
        plan = ExecutionPlan(
            source_branch="feature/x",
            base_branch="main",
            total_prs=1,
            prs=[PRPlan(
                index=1, title="PR #1", branch_name="stack/main/01",
                base_branch="main", files=["a.py"], depends_on=[],
                merge_strategy="squash", code_lines=10, risk_score=0.1,
            )],
            steps=[PlanStep(
                id=1, pr_index=1, phase="branch",
                description="Create branch",
                commands=["git checkout -b test main"],
            )],
        )
        data = plan.to_dict()
        loaded = ExecutionPlan.from_dict(data)
        self.assertEqual(loaded.source_branch, "feature/x")
        self.assertEqual(len(loaded.steps), 1)
        self.assertEqual(loaded.steps[0].commands, ["git checkout -b test main"])

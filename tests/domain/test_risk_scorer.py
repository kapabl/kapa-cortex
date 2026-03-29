"""Tests for risk scoring."""

import unittest
from src.domain.entity.changed_file import ChangedFile
from src.domain.entity.proposed_pr import ProposedPR
from src.domain.policy.risk_policy import compute_risk


def _make_file(path, added=10, removed=5):
    return ChangedFile(path=path, added=added, removed=removed, status="M")


class TestRiskScorer(unittest.TestCase):
    def test_low_risk(self):
        proposed_pr = ProposedPR(index=1, title="t", files=[_make_file("a.py", 5, 0)])
        self.assertLess(compute_risk(proposed_pr), 0.3)

    def test_high_risk(self):
        proposed_pr = ProposedPR(
            index=1, title="t",
            files=[_make_file(f"f{i}.py", 100, 50) for i in range(3)],
            depends_on=[2, 3, 4, 5, 6],
        )
        self.assertGreater(compute_risk(proposed_pr), 0.3)

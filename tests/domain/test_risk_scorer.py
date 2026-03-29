"""Tests for risk scoring."""

import unittest
from src.domain.changed_file import ChangedFile
from src.domain.proposed_pr import ProposedPR
from src.domain.risk_scorer import compute_risk


def _f(path, added=10, removed=5):
    return ChangedFile(path=path, added=added, removed=removed, status="M")


class TestRiskScorer(unittest.TestCase):
    def test_low_risk(self):
        pr = ProposedPR(index=1, title="t", files=[_f("a.py", 5, 0)])
        self.assertLess(compute_risk(pr), 0.3)

    def test_high_risk(self):
        pr = ProposedPR(
            index=1, title="t",
            files=[_f(f"f{i}.py", 100, 50) for i in range(3)],
            depends_on=[2, 3, 4, 5, 6],
        )
        self.assertGreater(compute_risk(pr), 0.3)

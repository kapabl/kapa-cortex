"""Tests for risk policy with structural ratio."""

import unittest

from src.domain.entity.changed_file import ChangedFile
from src.domain.entity.proposed_pr import ProposedPR
from src.domain.policy.risk_policy import compute_risk


class TestStructuralRatioImpact(unittest.TestCase):

    def test_cosmetic_changes_reduce_risk(self):
        """A PR with mostly cosmetic changes should score lower than all-structural."""
        structural_file = ChangedFile(
            path="src/core.py", added=200, removed=50, status="M",
            structural_ratio=1.0,
        )
        cosmetic_file = ChangedFile(
            path="src/core.py", added=200, removed=50, status="M",
            structural_ratio=0.1,
        )

        pr_structural = ProposedPR(index=1, title="", files=[structural_file])
        pr_cosmetic = ProposedPR(index=2, title="", files=[cosmetic_file])

        risk_structural = compute_risk(pr_structural)
        risk_cosmetic = compute_risk(pr_cosmetic)

        self.assertGreater(risk_structural, risk_cosmetic)

    def test_default_ratio_is_full_structural(self):
        """Default structural_ratio of 1.0 means no deflation."""
        changed_file = ChangedFile(path="src/a.py", added=100, removed=0, status="A")
        proposed_pr = ProposedPR(index=1, title="", files=[changed_file])
        risk = compute_risk(proposed_pr)
        self.assertGreater(risk, 0.0)


if __name__ == "__main__":
    unittest.main()

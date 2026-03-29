"""Tests for merge strategy assignment."""

import unittest
from src.domain.entity.changed_file import ChangedFile
from src.domain.entity.proposed_pr import ProposedPR
from src.domain.policy.merge_strategy_policy import assign_strategies


def _make_file(path, added=10, removed=5):
    return ChangedFile(path=path, added=added, removed=removed, status="M")


class TestMergeStrategy(unittest.TestCase):
    def test_depended_upon_gets_merge(self):
        pr1 = ProposedPR(index=1, title="PR #1", files=[_make_file("a.py")])
        pr2 = ProposedPR(index=2, title="PR #2", files=[_make_file("b.py")], depends_on=[1])
        assign_strategies([pr1, pr2])
        self.assertEqual(pr1.merge_strategy, "merge")
        self.assertEqual(pr2.merge_strategy, "squash")

    def test_docs_gets_rebase(self):
        proposed_pr = ProposedPR(index=1, title="PR #1", files=[_make_file("README.md")])
        assign_strategies([proposed_pr])
        self.assertEqual(proposed_pr.merge_strategy, "rebase")

    def test_standalone_gets_squash(self):
        proposed_pr = ProposedPR(index=1, title="PR #1", files=[_make_file("main.py")])
        assign_strategies([proposed_pr])
        self.assertEqual(proposed_pr.merge_strategy, "squash")

    def test_high_risk_gets_merge(self):
        proposed_pr = ProposedPR(index=1, title="PR #1", files=[_make_file("a.py")], risk_score=0.7)
        assign_strategies([proposed_pr])
        self.assertEqual(proposed_pr.merge_strategy, "merge")

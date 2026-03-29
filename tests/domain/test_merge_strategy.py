"""Tests for merge strategy assignment."""

import unittest
from src.domain.changed_file import ChangedFile
from src.domain.proposed_pr import ProposedPR
from src.domain.merge_strategy_assigner import assign_strategies


def _f(path, added=10, removed=5):
    return ChangedFile(path=path, added=added, removed=removed, status="M")


class TestMergeStrategy(unittest.TestCase):
    def test_depended_upon_gets_merge(self):
        pr1 = ProposedPR(index=1, title="PR #1", files=[_f("a.py")])
        pr2 = ProposedPR(index=2, title="PR #2", files=[_f("b.py")], depends_on=[1])
        assign_strategies([pr1, pr2])
        self.assertEqual(pr1.merge_strategy, "merge")
        self.assertEqual(pr2.merge_strategy, "squash")

    def test_docs_gets_rebase(self):
        pr = ProposedPR(index=1, title="PR #1", files=[_f("README.md")])
        assign_strategies([pr])
        self.assertEqual(pr.merge_strategy, "rebase")

    def test_standalone_gets_squash(self):
        pr = ProposedPR(index=1, title="PR #1", files=[_f("main.py")])
        assign_strategies([pr])
        self.assertEqual(pr.merge_strategy, "squash")

    def test_high_risk_gets_merge(self):
        pr = ProposedPR(index=1, title="PR #1", files=[_f("a.py")], risk_score=0.7)
        assign_strategies([pr])
        self.assertEqual(pr.merge_strategy, "merge")

"""Tests for DifftasticClassifier."""

import unittest

from src.infrastructure.diff.difftastic_classifier import (
    _reconstruct_sides,
    DifftasticClassifier,
)


class TestReconstructSides(unittest.TestCase):

    def test_extracts_old_and_new(self):
        diff = (
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,3 +1,3 @@\n"
            " context\n"
            "-old_line\n"
            "+new_line\n"
            " more_context\n"
        )
        old, new = _reconstruct_sides(diff)
        self.assertIn("old_line", old)
        self.assertIn("new_line", new)
        self.assertIn("context", old)
        self.assertIn("context", new)

    def test_empty_diff(self):
        old, new = _reconstruct_sides("")
        self.assertEqual(old, "")
        self.assertEqual(new, "")

    def test_additions_only(self):
        diff = (
            "@@ -0,0 +1,2 @@\n"
            "+line_one\n"
            "+line_two\n"
        )
        old, new = _reconstruct_sides(diff)
        self.assertEqual(old, "")
        self.assertIn("line_one", new)


class TestDifftasticClassifier(unittest.TestCase):

    def test_empty_diff_returns_one(self):
        c = DifftasticClassifier()
        self.assertEqual(c.structural_ratio("foo.py", ""), 1.0)

    def test_no_hunk_returns_one(self):
        c = DifftasticClassifier()
        # diff header only, no @@ hunks
        diff = "--- a/foo.py\n+++ b/foo.py\n"
        self.assertEqual(c.structural_ratio("foo.py", diff), 1.0)


if __name__ == "__main__":
    unittest.main()

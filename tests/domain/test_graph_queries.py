"""Tests for graph query services."""

import unittest

from src.domain.service.graph_queries import (
    find_impact, find_deps, find_hotspots,
)


class TestFindImpact(unittest.TestCase):

    def _build_graph(self):
        """
        a.py → b.py → c.py → d.py
                  ↘ e.py
        """
        reverse_edges = {
            "a.py": ["b.py"],
            "b.py": ["c.py"],
            "c.py": ["d.py"],
            "e.py": ["b.py"],
        }
        return lambda path: reverse_edges.get(path, [])

    def test_direct_dependents(self):
        result = find_impact("a.py", self._build_graph())
        self.assertEqual(result.direct, ["b.py"])

    def test_transitive_dependents(self):
        result = find_impact("a.py", self._build_graph())
        self.assertIn("c.py", result.transitive)
        self.assertIn("d.py", result.transitive)

    def test_total_affected(self):
        result = find_impact("a.py", self._build_graph())
        self.assertGreaterEqual(result.total_affected, 3)

    def test_no_dependents(self):
        result = find_impact("d.py", self._build_graph())
        self.assertEqual(result.direct, [])
        self.assertEqual(result.transitive, [])


class TestFindDeps(unittest.TestCase):

    def test_transitive_dependencies(self):
        forward_edges = {
            "d.py": ["c.py"],
            "c.py": ["b.py"],
            "b.py": ["a.py"],
        }
        get_deps = lambda path: forward_edges.get(path, [])

        result = find_deps("d.py", get_deps)
        self.assertIn("c.py", result)
        self.assertIn("b.py", result)
        self.assertIn("a.py", result)

    def test_no_dependencies(self):
        result = find_deps("leaf.py", lambda path: [])
        self.assertEqual(result, [])


class TestFindHotspots(unittest.TestCase):

    def test_ranks_by_complexity_times_dependents(self):
        files = ["a.py", "b.py", "c.py"]
        complexities = {"a.py": 20, "b.py": 5, "c.py": 10}
        dependents = {"a.py": ["x.py"], "b.py": ["x.py", "y.py", "z.py"], "c.py": []}

        result = find_hotspots(
            files,
            get_complexity=lambda path: complexities.get(path, 0),
            get_dependents=lambda path: dependents.get(path, []),
            limit=10,
        )

        self.assertEqual(len(result), 3)
        # a.py: 20 * (1+1) = 40, b.py: 5 * (1+3) = 20, c.py: 10 * (1+0) = 10
        self.assertEqual(result[0].path, "a.py")
        self.assertEqual(result[1].path, "b.py")
        self.assertEqual(result[2].path, "c.py")

    def test_limit(self):
        files = [f"file{index}.py" for index in range(50)]
        result = find_hotspots(
            files,
            get_complexity=lambda path: 5,
            get_dependents=lambda path: ["other.py"],
            limit=10,
        )
        self.assertEqual(len(result), 10)

    def test_skips_zero_complexity_zero_dependents(self):
        result = find_hotspots(
            ["empty.py"],
            get_complexity=lambda path: 0,
            get_dependents=lambda path: [],
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

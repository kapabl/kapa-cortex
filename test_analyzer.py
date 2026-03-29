#!/usr/bin/env python3
"""Unit tests for stacked_pr_analyzer and lang_parsers."""

import unittest
from unittest.mock import patch, MagicMock

import networkx as nx

from stacked_pr_analyzer import (
    ChangedFile,
    ProposedPR,
    build_dependency_graph,
    compute_pr_dependencies,
    compute_risk_scores,
    assign_merge_strategies,
    partition_into_prs,
    _path_to_module,
    generate_dot,
)
from lang_parsers import (
    ImportInfo,
    parse_imports,
    _parse_python_ast,
    _parse_cpp_regex,
    _parse_java_regex,
    _parse_kotlin_regex,
    _parse_go_regex,
    _parse_rust_regex,
    _parse_js_ts_regex,
    _parse_cmake_regex,
    _parse_buck2_regex,
    _parse_starlark_regex,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file(path, added=10, removed=5, status="M", diff_text=""):
    return ChangedFile(path=path, added=added, removed=removed, status=status, diff_text=diff_text)


# ---------------------------------------------------------------------------
# ChangedFile tests
# ---------------------------------------------------------------------------

class TestChangedFile(unittest.TestCase):
    def test_is_text_or_docs(self):
        self.assertTrue(_make_file("README.md").is_text_or_docs)
        self.assertTrue(_make_file("data.json").is_text_or_docs)
        self.assertTrue(_make_file("config.yaml").is_text_or_docs)
        self.assertFalse(_make_file("main.py").is_text_or_docs)
        self.assertFalse(_make_file("app.ts").is_text_or_docs)
        self.assertFalse(_make_file("lib.rs").is_text_or_docs)

    def test_code_lines(self):
        self.assertEqual(_make_file("a.py", added=30, removed=10).code_lines, 40)

    def test_module_key(self):
        self.assertEqual(_make_file("src/foo.py").module_key, "src")
        self.assertEqual(_make_file("setup.py").module_key, "__root__")

    def test_cyclomatic_complexity_default(self):
        self.assertEqual(_make_file("a.py").cyclomatic_complexity, 0)


# ---------------------------------------------------------------------------
# Path to module
# ---------------------------------------------------------------------------

class TestPathToModule(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(_path_to_module("src/utils/helpers.py"), "src.utils.helpers")

    def test_root(self):
        self.assertEqual(_path_to_module("main.py"), "main")


# ---------------------------------------------------------------------------
# Language parsers (regex fallbacks — always available)
# ---------------------------------------------------------------------------

class TestPythonParser(unittest.TestCase):
    def test_import(self):
        result = _parse_python_ast("import os\nimport sys")
        modules = {r.module for r in result}
        self.assertIn("os", modules)
        self.assertIn("sys", modules)

    def test_from_import(self):
        result = _parse_python_ast("from pathlib import Path\nfrom os.path import join")
        modules = {r.module for r in result}
        self.assertIn("pathlib", modules)
        self.assertIn("os.path", modules)

    def test_relative_import(self):
        result = _parse_python_ast("from .models import User")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].module, "models")


class TestCppParser(unittest.TestCase):
    def test_include_angle(self):
        result = _parse_cpp_regex('#include <iostream>\n#include <vector>')
        self.assertEqual(len(result), 2)

    def test_include_quotes(self):
        result = _parse_cpp_regex('#include "mylib/utils.h"')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].module, "mylib.utils")

    def test_preprocessor_spacing(self):
        result = _parse_cpp_regex('#  include <stdio.h>')
        self.assertEqual(len(result), 1)


class TestJavaParser(unittest.TestCase):
    def test_import(self):
        result = _parse_java_regex("import com.example.MyClass;")
        self.assertEqual(result[0].module, "com.example.MyClass")

    def test_static_import(self):
        result = _parse_java_regex("import static org.junit.Assert.assertEquals;")
        self.assertEqual(result[0].module, "org.junit.Assert.assertEquals")


class TestKotlinParser(unittest.TestCase):
    def test_import(self):
        result = _parse_kotlin_regex("import com.example.data.Repository")
        self.assertEqual(result[0].module, "com.example.data.Repository")


class TestGoParser(unittest.TestCase):
    def test_single_import(self):
        result = _parse_go_regex('import "fmt"')
        self.assertEqual(result[0].module, "fmt")

    def test_block_import(self):
        result = _parse_go_regex('import (\n  "fmt"\n  "os"\n  "strings"\n)')
        modules = {r.module for r in result}
        self.assertEqual(modules, {"fmt", "os", "strings"})


class TestRustParser(unittest.TestCase):
    def test_use(self):
        result = _parse_rust_regex("use std::collections::HashMap;")
        self.assertEqual(result[0].module, "std.collections.HashMap")

    def test_mod(self):
        result = _parse_rust_regex("mod utils;")
        self.assertEqual(result[0].module, "utils")

    def test_extern_crate(self):
        result = _parse_rust_regex("extern crate serde;")
        self.assertEqual(result[0].module, "serde")
        self.assertEqual(result[0].kind, "crate")


class TestJsTsParser(unittest.TestCase):
    def test_import_from(self):
        result = _parse_js_ts_regex("import { foo } from './utils'")
        self.assertEqual(result[0].module, "./utils")

    def test_require(self):
        result = _parse_js_ts_regex("const x = require('./config')")
        modules = {r.module for r in result}
        self.assertIn("./config", modules)


class TestCMakeParser(unittest.TestCase):
    def test_find_package(self):
        result = _parse_cmake_regex("find_package(Boost REQUIRED)")
        self.assertEqual(result[0].module, "Boost")

    def test_add_subdirectory(self):
        result = _parse_cmake_regex("add_subdirectory(src/core)")
        self.assertEqual(result[0].module, "src/core")


class TestBuck2Parser(unittest.TestCase):
    def test_load(self):
        result = _parse_buck2_regex('load("//tools:defs.bzl", "my_rule")')
        modules = {r.module for r in result}
        self.assertIn("//tools:defs.bzl", modules)

    def test_deps(self):
        result = _parse_buck2_regex('deps = [\n  "//lib:core",\n  "//lib:utils",\n]')
        modules = {r.module for r in result}
        self.assertIn("//lib:core", modules)
        self.assertIn("//lib:utils", modules)


class TestStarlarkParser(unittest.TestCase):
    def test_load(self):
        result = _parse_starlark_regex('load("@rules_cc//cc:defs.bzl", "cc_library")')
        self.assertEqual(result[0].module, "@rules_cc//cc:defs.bzl")


# ---------------------------------------------------------------------------
# Grouping / partitioning tests
# ---------------------------------------------------------------------------

class TestPartitioning(unittest.TestCase):
    def test_respects_max_files(self):
        files = [_make_file(f"src/f{i}.py", added=10, removed=0) for i in range(7)]
        G = nx.DiGraph()
        for f in files:
            G.add_node(f.path, file=f)
        prs = partition_into_prs(G, files, {}, max_files=3, max_code_lines=200)
        self.assertTrue(all(len(pr.files) <= 3 for pr in prs))
        self.assertEqual(sum(len(pr.files) for pr in prs), 7)

    def test_respects_max_lines(self):
        files = [_make_file(f"src/f{i}.py", added=150, removed=0) for i in range(3)]
        G = nx.DiGraph()
        for f in files:
            G.add_node(f.path, file=f)
        prs = partition_into_prs(G, files, {}, max_files=5, max_code_lines=200)
        self.assertTrue(len(prs) >= 2)

    def test_docs_exempt_from_line_limit(self):
        files = [
            _make_file("README.md", added=500, removed=0),
            _make_file("CHANGELOG.md", added=300, removed=0),
            _make_file("docs/guide.md", added=400, removed=0),
        ]
        G = nx.DiGraph()
        for f in files:
            G.add_node(f.path, file=f)
        prs = partition_into_prs(G, files, {}, max_files=3, max_code_lines=200)
        self.assertEqual(len(prs), 1)

    def test_empty_input(self):
        prs = partition_into_prs(nx.DiGraph(), [], {}, max_files=3, max_code_lines=200)
        self.assertEqual(prs, [])

    def test_affinity_groups_cochanging_files(self):
        files = [
            _make_file("src/a.py", added=10, removed=0),
            _make_file("src/b.py", added=10, removed=0),
            _make_file("lib/c.py", added=10, removed=0),
            _make_file("lib/d.py", added=10, removed=0),
        ]
        G = nx.DiGraph()
        for f in files:
            G.add_node(f.path, file=f)
        # a and b co-change frequently
        affinity = {("src/a.py", "src/b.py"): 1.0}
        prs = partition_into_prs(G, files, affinity, max_files=2, max_code_lines=200)
        # a and b should be in the same PR
        for pr in prs:
            paths = {f.path for f in pr.files}
            if "src/a.py" in paths:
                self.assertIn("src/b.py", paths)
                break


# ---------------------------------------------------------------------------
# PR dependencies
# ---------------------------------------------------------------------------

class TestPRDependencies(unittest.TestCase):
    def test_cross_pr_dependency(self):
        f1 = _make_file("src/models.py")
        f2 = _make_file("src/views.py")
        pr1 = ProposedPR(index=1, title="PR #1", files=[f1])
        pr2 = ProposedPR(index=2, title="PR #2", files=[f2])
        G = nx.DiGraph()
        G.add_edge("src/views.py", "src/models.py", kind="import")
        compute_pr_dependencies([pr1, pr2], G)
        self.assertEqual(pr2.depends_on, [1])
        self.assertEqual(pr1.depends_on, [])


# ---------------------------------------------------------------------------
# Risk scores
# ---------------------------------------------------------------------------

class TestRiskScores(unittest.TestCase):
    def test_low_risk(self):
        pr = ProposedPR(index=1, title="t", files=[_make_file("a.py", added=5, removed=0)])
        compute_risk_scores([pr])
        self.assertLess(pr.risk_score, 0.3)

    def test_high_risk(self):
        pr = ProposedPR(
            index=1, title="t",
            files=[_make_file(f"f{i}.py", added=100, removed=50) for i in range(3)],
            depends_on=[2, 3, 4, 5, 6],
        )
        compute_risk_scores([pr])
        self.assertGreater(pr.risk_score, 0.3)


# ---------------------------------------------------------------------------
# Merge strategies
# ---------------------------------------------------------------------------

class TestMergeStrategies(unittest.TestCase):
    def test_depended_upon_gets_merge(self):
        pr1 = ProposedPR(index=1, title="PR #1", files=[_make_file("a.py")])
        pr2 = ProposedPR(index=2, title="PR #2", files=[_make_file("b.py")], depends_on=[1])
        assign_merge_strategies([pr1, pr2])
        self.assertEqual(pr1.merge_strategy, "merge")
        self.assertEqual(pr2.merge_strategy, "squash")

    def test_docs_only_gets_rebase(self):
        pr = ProposedPR(index=1, title="PR #1", files=[_make_file("README.md")])
        assign_merge_strategies([pr])
        self.assertEqual(pr.merge_strategy, "rebase")

    def test_standalone_code_gets_squash(self):
        pr = ProposedPR(index=1, title="PR #1", files=[_make_file("main.py")])
        assign_merge_strategies([pr])
        self.assertEqual(pr.merge_strategy, "squash")

    def test_high_risk_gets_merge(self):
        pr = ProposedPR(index=1, title="PR #1", files=[_make_file("a.py")], risk_score=0.7)
        assign_merge_strategies([pr])
        self.assertEqual(pr.merge_strategy, "merge")


# ---------------------------------------------------------------------------
# DOT visualization
# ---------------------------------------------------------------------------

class TestVisualization(unittest.TestCase):
    def test_generate_dot(self):
        pr1 = ProposedPR(index=1, title="PR #1", files=[_make_file("a.py")], merge_strategy="squash", risk_score=0.1)
        pr2 = ProposedPR(index=2, title="PR #2", files=[_make_file("b.py")], depends_on=[1], merge_strategy="merge", risk_score=0.4)
        dot = generate_dot([pr1, pr2])
        self.assertIn("digraph", dot)
        self.assertIn("pr2 -> pr1", dot)
        self.assertIn("squash", dot)


if __name__ == "__main__":
    unittest.main()

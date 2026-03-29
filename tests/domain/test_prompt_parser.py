"""Tests for prompt parsing."""

import unittest
from src.domain.service.prompt_parser import parse_prompt


class TestPromptParser(unittest.TestCase):
    def test_gradle_keyword(self):
        rules = parse_prompt("gradle files")
        patterns = {r.pattern for r in rules}
        self.assertTrue(any("gradle" in p.lower() for p in patterns))

    def test_path_prefix(self):
        rules = parse_prompt("src/core/ changes")
        prefixes = [r for r in rules if r.kind == "path_prefix"]
        self.assertTrue(any(r.pattern == "src/core/" for r in prefixes))

    def test_glob(self):
        rules = parse_prompt("the *.bxl files")
        globs = [r for r in rules if r.kind == "glob"]
        self.assertTrue(any(r.pattern == "*.bxl" for r in globs))

    def test_cmake(self):
        rules = parse_prompt("all CMakeLists.txt changes")
        patterns = {r.pattern for r in rules}
        self.assertTrue(any("CMakeLists.txt" in p for p in patterns))

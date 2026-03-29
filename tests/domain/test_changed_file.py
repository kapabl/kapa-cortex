"""Tests for ChangedFile entity."""

import unittest
from src.domain.entity.changed_file import ChangedFile


class TestChangedFile(unittest.TestCase):
    def test_is_text_or_docs(self):
        self.assertTrue(ChangedFile("README.md", 10, 0, "M").is_text_or_docs)
        self.assertTrue(ChangedFile("data.json", 10, 0, "M").is_text_or_docs)
        self.assertFalse(ChangedFile("main.py", 10, 0, "M").is_text_or_docs)

    def test_code_lines(self):
        changed_file = ChangedFile("a.py", added=30, removed=10, status="M")
        self.assertEqual(changed_file.code_lines, 40)

    def test_module_key(self):
        self.assertEqual(ChangedFile("src/foo.py", 1, 0, "M").module_key, "src")
        self.assertEqual(ChangedFile("setup.py", 1, 0, "M").module_key, "__root__")

    def test_ext(self):
        self.assertEqual(ChangedFile("app.tsx", 1, 0, "M").ext, ".tsx")

    def test_cyclomatic_default(self):
        self.assertEqual(ChangedFile("a.py", 1, 0, "M").cyclomatic_complexity, 0)

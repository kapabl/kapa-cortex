"""Tests for FuzzyDefinitionResolver."""

import unittest

from src.infrastructure.lsp.fuzzy_resolver import FuzzyDefinitionResolver


class TestFuzzyResolver(unittest.TestCase):

    def test_resolves_module_name(self):
        resolver = FuzzyDefinitionResolver([
            "src/domain/entity/changed_file.py",
            "src/domain/service/dependency_resolver.py",
        ])
        result = resolver.resolve(
            "src/domain/service/dependency_resolver.py",
            "changed_file",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.file_path, "src/domain/entity/changed_file.py")

    def test_returns_none_for_unknown(self):
        resolver = FuzzyDefinitionResolver(["src/foo.py"])
        result = resolver.resolve("src/foo.py", "nonexistent_module")
        self.assertIsNone(result)

    def test_does_not_resolve_to_self(self):
        resolver = FuzzyDefinitionResolver(["src/foo.py"])
        result = resolver.resolve("src/foo.py", "foo")
        self.assertIsNone(result)

    def test_find_references_returns_empty(self):
        resolver = FuzzyDefinitionResolver(["src/foo.py"])
        result = resolver.find_references("src/foo.py", "anything")
        self.assertEqual(result, [])

    def test_dot_separated_module(self):
        resolver = FuzzyDefinitionResolver([
            "src/infrastructure/git/git_client.py",
        ])
        result = resolver.resolve("src/other.py", "src.infrastructure.git.git_client")
        self.assertIsNotNone(result)
        self.assertEqual(result.file_path, "src/infrastructure/git/git_client.py")


if __name__ == "__main__":
    unittest.main()

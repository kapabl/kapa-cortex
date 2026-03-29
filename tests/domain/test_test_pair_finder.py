"""Tests for test file pairing."""

import unittest
from src.domain.changed_file import ChangedFile
from src.domain.test_pair_finder import find_test_pairs


def _f(path):
    return ChangedFile(path=path, added=10, removed=0, status="M")


class TestTestPairFinder(unittest.TestCase):
    def test_python_prefix(self):
        pairs = find_test_pairs([_f("src/test_models.py"), _f("src/models.py")])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].impl_path, "src/models.py")

    def test_python_suffix(self):
        pairs = find_test_pairs([_f("src/models_test.py"), _f("src/models.py")])
        self.assertEqual(pairs[0].impl_path, "src/models.py")

    def test_go(self):
        pairs = find_test_pairs([_f("pkg/handler_test.go"), _f("pkg/handler.go")])
        self.assertEqual(pairs[0].impl_path, "pkg/handler.go")

    def test_js(self):
        pairs = find_test_pairs([_f("src/Button.test.tsx"), _f("src/Button.tsx")])
        self.assertEqual(pairs[0].impl_path, "src/Button.tsx")

    def test_java(self):
        pairs = find_test_pairs([_f("src/FooTest.java"), _f("src/Foo.java")])
        self.assertEqual(pairs[0].impl_path, "src/Foo.java")

    def test_cpp(self):
        pairs = find_test_pairs([_f("src/utils_test.cpp"), _f("src/utils.cpp")])
        self.assertEqual(pairs[0].impl_path, "src/utils.cpp")

    def test_no_pair_when_impl_missing(self):
        pairs = find_test_pairs([_f("src/test_models.py")])
        self.assertEqual(pairs, [])

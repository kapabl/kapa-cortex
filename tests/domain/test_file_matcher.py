"""Tests for file matching."""

import unittest
from src.domain.entity.changed_file import ChangedFile
from src.domain.value_object.extraction_rule import ExtractionRule
from src.domain.service.file_matcher import match_files


def _f(path, diff=""):
    return ChangedFile(path=path, added=10, removed=0, status="M", diff_text=diff)


class TestFileMatcher(unittest.TestCase):
    def test_glob(self):
        files = [_f("build.gradle"), _f("src/main.py")]
        rules = [ExtractionRule("glob", "*.gradle", "")]
        matched = match_files(files, rules)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].path, "build.gradle")

    def test_ext(self):
        files = [_f("a.py"), _f("b.py"), _f("c.java")]
        rules = [ExtractionRule("ext", ".py", "")]
        matched = match_files(files, rules)
        self.assertEqual(len(matched), 2)

    def test_path_prefix(self):
        files = [_f("src/core/a.py"), _f("src/ui/b.py")]
        rules = [ExtractionRule("path_prefix", "src/core/", "")]
        matched = match_files(files, rules)
        self.assertEqual(matched[0].path, "src/core/a.py")

    def test_keyword_in_diff(self):
        files = [_f("setup.py", diff="+init-script"), _f("main.py")]
        rules = [ExtractionRule("keyword", "init-script", "")]
        matched = match_files(files, rules)
        self.assertEqual(len(matched), 1)

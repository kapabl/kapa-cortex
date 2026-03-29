"""Tests for PR title generation from code changes."""

import unittest
from src.domain.changed_file import ChangedFile
from src.domain.pr_namer import generate_title


def _f(path, status="M", diff=""):
    return ChangedFile(path=path, added=10, removed=0, status=status, diff_text=diff)


class TestPRNamer(unittest.TestCase):
    def test_docs_only(self):
        title = generate_title([_f("README.md"), _f("CHANGELOG.md")])
        self.assertIn("docs", title.lower())

    def test_deleted_files(self):
        title = generate_title([_f("old/module.py", status="D")])
        self.assertIn("Remove", title)

    def test_new_class(self):
        diff = "+++ b/auth.py\n+class AuthManager:\n+    pass"
        title = generate_title([_f("src/auth.py", status="A", diff=diff)])
        self.assertIn("AuthManager", title)

    def test_new_function(self):
        diff = "+++ b/utils.py\n+def validate_token(token):\n+    pass"
        title = generate_title([_f("src/utils.py", diff=diff)])
        self.assertIn("validate_token", title)

    def test_module_fallback(self):
        title = generate_title([_f("src/config.py")])
        self.assertIn("src", title.lower())

    def test_empty(self):
        self.assertEqual(generate_title([]), "Empty PR")

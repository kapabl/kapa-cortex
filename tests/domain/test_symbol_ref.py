"""Tests for SymbolRef entity."""

import unittest

from src.domain.entity.symbol_ref import SymbolRef


class TestSymbolRef(unittest.TestCase):

    def test_create_with_defaults(self):
        ref = SymbolRef(name="Foo")
        self.assertEqual(ref.name, "Foo")
        self.assertEqual(ref.kind, "")
        self.assertEqual(ref.line, 0)

    def test_create_with_all_fields(self):
        ref = SymbolRef(name="bar", kind="call", line=42)
        self.assertEqual(ref.name, "bar")
        self.assertEqual(ref.kind, "call")
        self.assertEqual(ref.line, 42)

    def test_frozen(self):
        ref = SymbolRef(name="Foo")
        with self.assertRaises(AttributeError):
            ref.name = "Bar"

    def test_equality(self):
        a = SymbolRef(name="Foo", kind="call", line=10)
        b = SymbolRef(name="Foo", kind="call", line=10)
        self.assertEqual(a, b)

    def test_usable_in_set(self):
        refs = {SymbolRef(name="Foo"), SymbolRef(name="Foo"), SymbolRef(name="Bar")}
        self.assertEqual(len(refs), 2)


if __name__ == "__main__":
    unittest.main()

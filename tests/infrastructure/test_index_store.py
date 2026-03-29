"""Tests for IndexStore."""

import tempfile
import unittest

from src.infrastructure.indexer.index_store import (
    IndexStore, FileEntry, SymbolEntry, ImportEntry, EdgeEntry,
)


class TestIndexStore(unittest.TestCase):

    def _build_store(self):
        store = IndexStore()
        store.add_file(FileEntry("src/a.py", "python", "abc123", 100, 5))
        store.add_file(FileEntry("src/b.py", "python", "def456", 50, 2))
        store.add_symbols("src/a.py", [
            SymbolEntry("Foo", "class", 10, "", "src/a.py"),
            SymbolEntry("bar", "function", 20, "", "src/a.py"),
        ])
        store.add_imports("src/b.py", [
            ImportEntry("from src.a import Foo", "src.a", "module", "src/b.py"),
        ])
        store.add_edge(EdgeEntry("src/b.py", "src/a.py", "import", 1.0))
        return store

    def test_file_count(self):
        store = self._build_store()
        self.assertEqual(store.file_count, 2)

    def test_symbol_count(self):
        store = self._build_store()
        self.assertEqual(store.symbol_count, 2)

    def test_get_symbols_for_file(self):
        store = self._build_store()
        symbols = store.get_symbols_for_file("src/a.py")
        self.assertEqual(len(symbols), 2)
        self.assertEqual(symbols[0].name, "Foo")

    def test_get_files_defining_symbol(self):
        store = self._build_store()
        files = store.get_files_defining_symbol("Foo")
        self.assertEqual(files, ["src/a.py"])

    def test_get_dependents(self):
        store = self._build_store()
        dependents = store.get_dependents("src/a.py")
        self.assertEqual(dependents, ["src/b.py"])

    def test_get_dependencies(self):
        store = self._build_store()
        deps = store.get_dependencies("src/b.py")
        self.assertEqual(deps, ["src/a.py"])

    def test_remove_file(self):
        store = self._build_store()
        store.remove_file("src/a.py")
        self.assertEqual(store.file_count, 1)
        self.assertEqual(store.get_files_defining_symbol("Foo"), [])
        self.assertEqual(store.edge_count, 0)

    def test_save_and_load(self):
        store = self._build_store()
        with tempfile.NamedTemporaryFile(suffix=".msgpack", delete=False) as tmp_file:
            path = tmp_file.name

        store.save(path)
        loaded = IndexStore.load(path)

        self.assertEqual(loaded.file_count, 2)
        self.assertEqual(loaded.symbol_count, 2)
        self.assertEqual(loaded.edge_count, 1)
        self.assertEqual(loaded.get_dependents("src/a.py"), ["src/b.py"])

    def test_empty_store(self):
        store = IndexStore()
        self.assertEqual(store.file_count, 0)
        self.assertEqual(store.symbol_count, 0)
        self.assertEqual(store.edge_count, 0)
        self.assertEqual(store.get_dependents("nope"), [])


if __name__ == "__main__":
    unittest.main()

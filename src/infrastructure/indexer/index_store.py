"""In-memory index store — the daemon's core data structure."""

from __future__ import annotations

import hashlib
import msgpack
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileEntry:
    """Indexed file metadata."""
    path: str
    language: str
    file_hash: str
    lines: int = 0
    complexity: int = 0


@dataclass
class SymbolEntry:
    """Symbol defined in a file."""
    name: str
    kind: str
    line: int
    scope: str
    file_path: str


@dataclass
class ImportEntry:
    """Import/dependency from a file."""
    raw: str
    module: str
    kind: str
    file_path: str


@dataclass
class EdgeEntry:
    """Dependency edge between files."""
    source: str
    target: str
    kind: str
    weight: float


class IndexStore:
    """In-memory index of files, symbols, imports, and edges."""

    def __init__(self):
        self.files: dict[str, FileEntry] = {}
        self.symbols: dict[str, list[SymbolEntry]] = {}  # file_path → symbols
        self.imports: dict[str, list[ImportEntry]] = {}   # file_path → imports
        self.edges: list[EdgeEntry] = []
        self._symbol_index: dict[str, list[str]] = {}     # symbol_name → file_paths

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def symbol_count(self) -> int:
        return sum(len(syms) for syms in self.symbols.values())

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def add_file(self, entry: FileEntry) -> None:
        self.files[entry.path] = entry

    def add_symbols(self, file_path: str, entries: list[SymbolEntry]) -> None:
        self.symbols[file_path] = entries
        for symbol in entries:
            self._symbol_index.setdefault(symbol.name, []).append(file_path)

    def add_imports(self, file_path: str, entries: list[ImportEntry]) -> None:
        self.imports[file_path] = entries

    def add_edge(self, edge: EdgeEntry) -> None:
        self.edges.append(edge)

    def remove_file(self, file_path: str) -> None:
        """Remove a file and all its associated data."""
        self.files.pop(file_path, None)
        old_symbols = self.symbols.pop(file_path, [])
        for symbol in old_symbols:
            paths = self._symbol_index.get(symbol.name, [])
            self._symbol_index[symbol.name] = [
                path for path in paths if path != file_path
            ]
        self.imports.pop(file_path, None)
        self.edges = [
            edge for edge in self.edges
            if edge.source != file_path and edge.target != file_path
        ]

    def get_symbols_for_file(self, file_path: str) -> list[SymbolEntry]:
        return self.symbols.get(file_path, [])

    def get_imports_for_file(self, file_path: str) -> list[ImportEntry]:
        return self.imports.get(file_path, [])

    def get_files_defining_symbol(self, symbol_name: str) -> list[str]:
        return self._symbol_index.get(symbol_name, [])

    def get_dependents(self, file_path: str) -> list[str]:
        """Files that depend on the given file (reverse edges)."""
        return [
            edge.source for edge in self.edges
            if edge.target == file_path
        ]

    def get_dependencies(self, file_path: str) -> list[str]:
        """Files that the given file depends on (forward edges)."""
        return [
            edge.target for edge in self.edges
            if edge.source == file_path
        ]

    def save(self, path: str) -> None:
        """Persist index to MessagePack file."""
        data = {
            "files": {
                file_path: {
                    "language": entry.language,
                    "file_hash": entry.file_hash,
                    "lines": entry.lines,
                    "complexity": entry.complexity,
                }
                for file_path, entry in self.files.items()
            },
            "symbols": {
                file_path: [
                    {"name": sym.name, "kind": sym.kind, "line": sym.line, "scope": sym.scope}
                    for sym in syms
                ]
                for file_path, syms in self.symbols.items()
            },
            "imports": {
                file_path: [
                    {"raw": imp.raw, "module": imp.module, "kind": imp.kind}
                    for imp in imps
                ]
                for file_path, imps in self.imports.items()
            },
            "edges": [
                {"source": edge.source, "target": edge.target,
                 "kind": edge.kind, "weight": edge.weight}
                for edge in self.edges
            ],
        }
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(msgpack.packb(data, use_bin_type=True))

    @classmethod
    def load(cls, path: str) -> IndexStore:
        """Load index from MessagePack file."""
        raw = Path(path).read_bytes()
        data = msgpack.unpackb(raw, raw=False)

        store = cls()

        for file_path, file_data in data.get("files", {}).items():
            store.add_file(FileEntry(
                path=file_path,
                language=file_data["language"],
                file_hash=file_data["file_hash"],
                lines=file_data.get("lines", 0),
                complexity=file_data.get("complexity", 0),
            ))

        for file_path, sym_list in data.get("symbols", {}).items():
            entries = [
                SymbolEntry(
                    name=sym["name"], kind=sym["kind"],
                    line=sym.get("line", 0), scope=sym.get("scope", ""),
                    file_path=file_path,
                )
                for sym in sym_list
            ]
            store.add_symbols(file_path, entries)

        for file_path, imp_list in data.get("imports", {}).items():
            entries = [
                ImportEntry(
                    raw=imp["raw"], module=imp["module"],
                    kind=imp.get("kind", ""), file_path=file_path,
                )
                for imp in imp_list
            ]
            store.add_imports(file_path, entries)

        for edge_data in data.get("edges", []):
            store.add_edge(EdgeEntry(
                source=edge_data["source"], target=edge_data["target"],
                kind=edge_data["kind"], weight=edge_data["weight"],
            ))

        return store


def compute_file_hash(file_path: str) -> str:
    """Compute MD5 hash of a file for change detection."""
    try:
        content = Path(file_path).read_bytes()
        return hashlib.md5(content).hexdigest()
    except (FileNotFoundError, PermissionError):
        return ""

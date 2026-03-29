"""Domain service: build file dependency graph from import/symbol data."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from src.domain.entity.changed_file import ChangedFile
from src.domain.value_object.import_ref import ImportRef
from src.domain.value_object.symbol_def import SymbolDef


def build_dependency_edges(
    files: list[ChangedFile],
    imports_by_file: dict[str, list[ImportRef]],
) -> list[tuple[str, str, str, float]]:
    """
    Build (source, target, kind, weight) edges.
    source depends on target: target must land first.
    """
    module_index = _build_module_index(files)
    symbol_index = _build_symbol_index(files)
    edges: list[tuple[str, str, str, float]] = []

    edges.extend(_import_edges(files, imports_by_file, module_index))
    edges.extend(_symbol_edges(files, symbol_index))

    return edges


def _build_module_index(files: list[ChangedFile]) -> dict[str, str]:
    """Map module-like keys to file paths."""
    index: dict[str, str] = {}
    for f in files:
        mod = _path_to_module(f.path)
        index[mod] = f.path
        short = mod.rsplit(".", 1)[-1]
        index.setdefault(short, f.path)
        dir_mod = _path_to_module(str(Path(f.path).parent))
        if dir_mod and dir_mod != ".":
            index.setdefault(dir_mod, f.path)
    return index


def _build_symbol_index(
    files: list[ChangedFile],
) -> dict[str, set[str]]:
    """Map symbol names to file paths that define them."""
    index: defaultdict[str, set[str]] = defaultdict(set)
    for f in files:
        for sym in f.symbols_defined:
            index[sym.name].add(f.path)
    return dict(index)


def _import_edges(
    files: list[ChangedFile],
    imports_by_file: dict[str, list[ImportRef]],
    module_index: dict[str, str],
) -> list[tuple[str, str, str, float]]:
    """Edges from import analysis."""
    edges = []
    for f in files:
        for imp in imports_by_file.get(f.path, []):
            norm = _normalize_import(imp.module)
            target = _resolve_target(norm, f.path, module_index)
            if target:
                edges.append((f.path, target, "import", 1.0))
    return edges


def _symbol_edges(
    files: list[ChangedFile],
    symbol_index: dict[str, set[str]],
) -> list[tuple[str, str, str, float]]:
    """Edges from symbol usage analysis."""
    edges = []
    for f in files:
        for sym_name in f.symbols_used:
            for provider in symbol_index.get(sym_name, set()):
                if provider != f.path:
                    edges.append((f.path, provider, "symbol", 0.8))
    return edges


def _resolve_target(
    norm: str,
    source_path: str,
    module_index: dict[str, str],
) -> str | None:
    """Find the file a normalized import refers to."""
    for key, target in module_index.items():
        if target == source_path:
            continue
        if norm == key or norm.endswith(f".{key}") or key.endswith(f".{norm}"):
            return target
    return None


def _normalize_import(raw: str) -> str:
    return raw.replace("/", ".").replace("::", ".").lstrip(".")


def _path_to_module(path: str) -> str:
    p = Path(path).with_suffix("")
    return str(p).replace("/", ".").replace("\\", ".")

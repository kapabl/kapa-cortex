"""Fuzzy definition resolver — standalone fallback without LSP."""

from __future__ import annotations

from pathlib import Path

from src.domain.port.definition_resolver import DefinitionLocation, DefinitionResolver


class FuzzyDefinitionResolver(DefinitionResolver):
    """Resolve symbols by fuzzy module name matching. No LSP needed."""

    def __init__(self, file_paths: list[str]):
        self._module_index = _build_module_index(file_paths)

    def resolve(
        self, file_path: str, symbol_name: str, line: int = 0,
    ) -> DefinitionLocation | None:
        target = _fuzzy_match(symbol_name, file_path, self._module_index)
        if target:
            return DefinitionLocation(file_path=target)
        return None

    def find_references(
        self, file_path: str, symbol_name: str, line: int = 0,
    ) -> list[DefinitionLocation]:
        # Fuzzy resolver can't find references — only definitions
        return []


def _build_module_index(file_paths: list[str]) -> dict[str, str]:
    """Map module-like keys to file paths."""
    index: dict[str, str] = {}
    for path in file_paths:
        mod = _path_to_module(path)
        index[mod] = path
        short = mod.rsplit(".", 1)[-1]
        index.setdefault(short, path)
        dir_mod = _path_to_module(str(Path(path).parent))
        if dir_mod and dir_mod != ".":
            index.setdefault(dir_mod, path)
    return index


def _fuzzy_match(
    symbol: str, source_path: str, module_index: dict[str, str],
) -> str | None:
    """Find the file a symbol refers to via fuzzy matching."""
    normalized = symbol.replace("/", ".").replace("::", ".").lstrip(".")
    for key, target in module_index.items():
        if target == source_path:
            continue
        if normalized == key or normalized.endswith(f".{key}") or key.endswith(f".{normalized}"):
            return target
    return None


def _path_to_module(path: str) -> str:
    module_path = Path(path).with_suffix("")
    return str(module_path).replace("/", ".").replace("\\", ".")

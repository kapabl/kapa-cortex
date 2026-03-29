"""Pre-compute and cache import graphs for all source files."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from src.infrastructure.parsers.import_dispatcher import dispatch_parse_imports

CACHE_FILE = ".cortex-cache/imports.json"


def build_import_index(
    file_paths: list[str],
    root: str = ".",
) -> dict[str, list[dict]]:
    """
    Parse imports for all files, cache the result.
    Returns {file_path: [{raw, module, kind}, ...]}.
    """
    cache_path = Path(root) / CACHE_FILE
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    existing = _load_cache(cache_path)
    hashes = _compute_hashes(file_paths)
    result: dict[str, list[dict]] = {}

    total_files = len(file_paths)
    parsed_count = 0
    cached_count = 0

    for index, path in enumerate(file_paths, 1):
        file_hash = hashes.get(path, "")
        cached = existing.get(path)

        if cached and cached.get("hash") == file_hash:
            result[path] = cached["imports"]
            cached_count += 1
            continue

        source = _read_file(path)
        if not source:
            continue

        imports = dispatch_parse_imports(path, source)
        result[path] = [
            {"raw": imp.raw, "module": imp.module, "kind": imp.kind}
            for imp in imports
        ]
        parsed_count += 1

        if index % 200 == 0 or index == total_files:
            _report_progress(index, total_files, cached_count, parsed_count)

    _save_cache(cache_path, result, hashes)
    return result


def _report_progress(index, total, cached, parsed):
    try:
        from src.infrastructure.indexer.index_all import set_progress
        set_progress(f"{index}/{total}  ({cached} cached, {parsed} parsed)")
    except ImportError:
        pass


def load_import_cache(root: str = ".") -> dict[str, list[dict]] | None:
    cache_path = Path(root) / CACHE_FILE
    if cache_path.exists():
        data = json.loads(cache_path.read_text())
        return {k: v.get("imports", []) for k, v in data.items()}
    return None


def _load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_cache(path: Path, result: dict, hashes: dict) -> None:
    data = {}
    for file_path, imports in result.items():
        data[file_path] = {
            "hash": hashes.get(file_path, ""),
            "imports": imports,
        }
    path.write_text(json.dumps(data, indent=2))


def _compute_hashes(file_paths: list[str]) -> dict[str, str]:
    result = {}
    for path in file_paths:
        try:
            content = Path(path).read_bytes()
            result[path] = hashlib.md5(content).hexdigest()
        except (FileNotFoundError, PermissionError):
            pass
    return result


def _read_file(path: str) -> str:
    try:
        return Path(path).read_text(errors="replace")
    except (FileNotFoundError, PermissionError):
        return ""

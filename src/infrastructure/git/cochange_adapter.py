"""Infrastructure: co-change provider with cache-first strategy."""

from __future__ import annotations

import subprocess

from src.domain.port.cochange_provider import CochangeProvider
from src.infrastructure.indexer.cochange_cache import load_cochange_cache


class CachedCochangeProvider(CochangeProvider):
    """Loads co-change data from cache, falls back to git log."""

    def __init__(self, root: str = "."):
        self._root = root

    def cochange_history(
        self, paths: list[str],
    ) -> dict[tuple[str, str], int]:
        cached = load_cochange_cache(self._root)
        if cached is not None:
            return _filter_cached(cached, paths)
        return _analyze_from_git(paths)


def _filter_cached(
    cache: dict[str, int],
    paths: list[str],
) -> dict[tuple[str, str], int]:
    """Filter cached co-change matrix to requested paths."""
    path_set = set(paths)
    result: dict[tuple[str, str], int] = {}
    for key, count in cache.items():
        parts = key.split("::")
        if len(parts) != 2:
            continue
        a, b = parts
        if a in path_set and b in path_set:
            result[(a, b)] = count
    return result


def _analyze_from_git(
    paths: list[str],
    max_commits: int = 200,
) -> dict[tuple[str, str], int]:
    """Fallback: analyze git log at runtime."""
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={max_commits}",
             "--name-only", "--format="],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}

    path_set = set(paths)
    cochange: dict[tuple[str, str], int] = {}
    commit_files: list[str] = []

    for line in result.stdout.splitlines():
        if not line.strip():
            _count_pairs(commit_files, path_set, cochange)
            commit_files = []
        elif line.strip() in path_set:
            commit_files.append(line.strip())

    _count_pairs(commit_files, path_set, cochange)
    return cochange


def _count_pairs(
    files: list[str],
    path_set: set[str],
    cochange: dict[tuple[str, str], int],
) -> None:
    relevant = [file for file in files if file in path_set]
    for i, a in enumerate(relevant):
        for b in relevant[i + 1:]:
            pair = tuple(sorted([a, b]))
            cochange[pair] = cochange.get(pair, 0) + 1

"""Domain service: graph queries on the dependency index."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass
class ImpactResult:
    """Result of an impact analysis query."""
    target: str
    direct: list[str]
    transitive: list[str]

    @property
    def total_affected(self) -> int:
        return len(self.direct) + len(self.transitive)


@dataclass
class HotspotEntry:
    """A file ranked by risk — high complexity + many dependents."""
    path: str
    complexity: int
    dependent_count: int
    score: float


def find_impact(
    target_path: str,
    get_dependents: callable,
) -> ImpactResult:
    """Find all files affected by changes to target_path.

    Uses BFS to walk reverse edges (who depends on this file).
    """
    direct = get_dependents(target_path)
    transitive = _bfs_reverse(target_path, get_dependents, max_depth=10)
    transitive_only = [
        path for path in transitive
        if path not in direct and path != target_path
    ]

    return ImpactResult(
        target=target_path,
        direct=direct,
        transitive=transitive_only,
    )


def find_deps(
    target_path: str,
    get_dependencies: callable,
) -> list[str]:
    """Find all transitive dependencies of target_path.

    Uses BFS to walk forward edges (what does this file depend on).
    """
    return _bfs_forward(target_path, get_dependencies, max_depth=10)


def find_hotspots(
    file_paths: list[str],
    get_complexity: callable,
    get_dependents: callable,
    limit: int = 20,
) -> list[HotspotEntry]:
    """Rank files by complexity × dependent count.

    Files that are both complex and heavily depended upon
    are the riskiest to change — they're hotspots.
    """
    entries: list[HotspotEntry] = []

    for path in file_paths:
        complexity = get_complexity(path)
        dependent_count = len(get_dependents(path))
        if complexity == 0 and dependent_count == 0:
            continue
        score = complexity * (1 + dependent_count)
        entries.append(HotspotEntry(
            path=path,
            complexity=complexity,
            dependent_count=dependent_count,
            score=score,
        ))

    entries.sort(key=lambda entry: entry.score, reverse=True)
    return entries[:limit]


def _bfs_reverse(
    start: str,
    get_dependents: callable,
    max_depth: int,
) -> list[str]:
    """BFS over reverse dependency edges."""
    visited: set[str] = {start}
    queue: list[tuple[str, int]] = [(start, 0)]
    result: list[str] = []

    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for dependent in get_dependents(current):
            if dependent not in visited:
                visited.add(dependent)
                result.append(dependent)
                queue.append((dependent, depth + 1))

    return result


def _bfs_forward(
    start: str,
    get_dependencies: callable,
    max_depth: int,
) -> list[str]:
    """BFS over forward dependency edges."""
    visited: set[str] = {start}
    queue: list[tuple[str, int]] = [(start, 0)]
    result: list[str] = []

    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        for dependency in get_dependencies(current):
            if dependency not in visited:
                visited.add(dependency)
                result.append(dependency)
                queue.append((dependency, depth + 1))

    return result

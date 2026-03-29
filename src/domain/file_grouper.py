"""Domain service: partition files into PR-sized groups."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from src.domain.changed_file import ChangedFile
from src.domain.proposed_pr import ProposedPR
from src.domain.test_pair import TestPair


def partition(
    files: list[ChangedFile],
    topo_order: list[str],
    test_pairs: list[TestPair],
    affinity: dict[tuple[str, str], float],
    max_files: int = 3,
    max_code_lines: int = 200,
) -> list[ProposedPR]:
    """
    Partition changed files into PR-sized groups.

    Respects:
      1. Topological ordering (deps first)
      2. Test↔implementation pairing (hard constraint)
      3. Co-change affinity (soft preference)
      4. File count and line count budgets
    """
    if not files:
        return []

    file_map = {f.path: f for f in files}
    impl_to_tests = _build_impl_to_tests(test_pairs)
    test_to_impl = {tp.test_path: tp.impl_path for tp in test_pairs}
    ordered = _build_ordered_paths(files, file_map, topo_order)

    prs: list[ProposedPR] = []
    assigned: set[str] = set()
    current: Optional[ProposedPR] = None

    for path in ordered:
        if path in assigned or path not in file_map:
            continue

        f = file_map[path]
        code = 0 if f.is_text_or_docs else f.code_lines

        can_fit = (
            current is not None
            and len(current.files) < max_files
            and (f.is_text_or_docs
                 or current.total_code_lines + code <= max_code_lines
                 or current.total_code_lines == 0)
        )

        if not can_fit:
            best = _find_affinity_pr(prs, path, f, affinity, file_map, max_files, max_code_lines)
            current = best if best else _start_pr(prs)

        current.files.append(f)
        assigned.add(path)
        _pull_paired_files(current, path, impl_to_tests, test_to_impl, file_map, assigned)

    for pr in prs:
        pr.title = f"PR #{pr.index}: {_label(pr.files)}"

    return prs


def _build_impl_to_tests(
    pairs: list[TestPair],
) -> dict[str, list[str]]:
    result: defaultdict[str, list[str]] = defaultdict(list)
    for tp in pairs:
        result[tp.impl_path].append(tp.test_path)
    return dict(result)


def _build_ordered_paths(
    files: list[ChangedFile],
    file_map: dict[str, ChangedFile],
    topo_order: list[str],
) -> list[str]:
    all_paths = {f.path for f in files}
    remaining = all_paths - set(topo_order)
    remaining_sorted = sorted(
        remaining,
        key=lambda p: (not file_map[p].is_text_or_docs, file_map[p].module_key, p),
    )
    return topo_order + remaining_sorted


def _start_pr(prs: list[ProposedPR]) -> ProposedPR:
    pr = ProposedPR(index=len(prs) + 1, title="", files=[])
    prs.append(pr)
    return pr


def _find_affinity_pr(
    prs: list[ProposedPR],
    path: str,
    f: ChangedFile,
    affinity: dict[tuple[str, str], float],
    file_map: dict[str, ChangedFile],
    max_files: int,
    max_code_lines: int,
) -> Optional[ProposedPR]:
    code = 0 if f.is_text_or_docs else f.code_lines
    best_pr = None
    best_score = 0.0

    for pr in prs:
        if len(pr.files) >= max_files:
            continue
        if not f.is_text_or_docs and pr.total_code_lines + code > max_code_lines and pr.total_code_lines > 0:
            continue
        score = _pr_affinity(pr, path, affinity, file_map)
        if score > best_score:
            best_score = score
            best_pr = pr

    return best_pr if best_score > 0.3 else None


def _pr_affinity(
    pr: ProposedPR,
    path: str,
    affinity: dict[tuple[str, str], float],
    file_map: dict[str, ChangedFile],
) -> float:
    score = 0.0
    target = file_map.get(path)
    if not target:
        return 0.0

    for existing in pr.files:
        pair = tuple(sorted([existing.path, path]))
        score += affinity.get(pair, 0.0)
        if Path(existing.path).parent == Path(path).parent:
            score += 0.3
        if existing.module_key == target.module_key:
            score += 0.2
    return score


def _pull_paired_files(
    pr: ProposedPR,
    path: str,
    impl_to_tests: dict[str, list[str]],
    test_to_impl: dict[str, str],
    file_map: dict[str, ChangedFile],
    assigned: set[str],
) -> None:
    for test_path in impl_to_tests.get(path, []):
        if test_path not in assigned and test_path in file_map:
            pr.files.append(file_map[test_path])
            assigned.add(test_path)
    impl_path = test_to_impl.get(path)
    if impl_path and impl_path not in assigned and impl_path in file_map:
        pr.files.append(file_map[impl_path])
        assigned.add(impl_path)


def _label(files: list[ChangedFile]) -> str:
    modules = {f.module_key for f in files}
    if all(f.is_text_or_docs for f in files):
        return "docs/config updates"
    if len(modules) == 1:
        mod = next(iter(modules))
        return "root-level changes" if mod == "__root__" else f"{mod} changes"
    return "cross-module changes"

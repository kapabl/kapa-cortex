"""Factory: partition files into PR-sized groups."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from src.domain.entity.changed_file import ChangedFile
from src.domain.entity.proposed_pr import ProposedPR
from src.domain.value_object.test_pair import TestPair


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

    file_map = {file.path: file for file in files}
    impl_to_tests = _build_impl_to_tests(test_pairs)
    test_to_impl = {test_pair.test_path: test_pair.impl_path for test_pair in test_pairs}
    ordered = _build_ordered_paths(files, file_map, topo_order)

    prs: list[ProposedPR] = []
    assigned: set[str] = set()
    current: Optional[ProposedPR] = None

    for path in ordered:
        if path in assigned or path not in file_map:
            continue

        changed_file = file_map[path]
        code = 0 if changed_file.is_text_or_docs else changed_file.code_lines

        can_fit = (
            current is not None
            and len(current.files) < max_files
            and (changed_file.is_text_or_docs
                 or current.total_code_lines + code <= max_code_lines
                 or current.total_code_lines == 0)
        )

        if not can_fit:
            best = _find_affinity_pr(prs, path, changed_file, affinity, file_map, max_files, max_code_lines)
            current = best if best else _start_pr(prs)

        current.files.append(changed_file)
        assigned.add(path)
        _pull_paired_files(current, path, impl_to_tests, test_to_impl, file_map, assigned)

    for proposed_pr in prs:
        proposed_pr.title = f"PR #{proposed_pr.index}: {_label(proposed_pr.files)}"

    return prs


def _build_impl_to_tests(
    pairs: list[TestPair],
) -> dict[str, list[str]]:
    result: defaultdict[str, list[str]] = defaultdict(list)
    for test_pair in pairs:
        result[test_pair.impl_path].append(test_pair.test_path)
    return dict(result)


def _build_ordered_paths(
    files: list[ChangedFile],
    file_map: dict[str, ChangedFile],
    topo_order: list[str],
) -> list[str]:
    all_paths = {file.path for file in files}
    remaining = all_paths - set(topo_order)
    remaining_sorted = sorted(
        remaining,
        key=lambda path: (not file_map[path].is_text_or_docs, file_map[path].module_key, path),
    )
    return topo_order + remaining_sorted


def _start_pr(prs: list[ProposedPR]) -> ProposedPR:
    proposed_pr = ProposedPR(index=len(prs) + 1, title="", files=[])
    prs.append(proposed_pr)
    return proposed_pr


def _find_affinity_pr(
    prs: list[ProposedPR],
    path: str,
    changed_file: ChangedFile,
    affinity: dict[tuple[str, str], float],
    file_map: dict[str, ChangedFile],
    max_files: int,
    max_code_lines: int,
) -> Optional[ProposedPR]:
    code = 0 if changed_file.is_text_or_docs else changed_file.code_lines
    best_pr = None
    best_score = 0.0

    for candidate in prs:
        if len(candidate.files) >= max_files:
            continue
        if not changed_file.is_text_or_docs and candidate.total_code_lines + code > max_code_lines and candidate.total_code_lines > 0:
            continue
        score = _pr_affinity(candidate, path, affinity, file_map)
        if score > best_score:
            best_score = score
            best_pr = candidate

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
    modules = {file.module_key for file in files}
    if all(file.is_text_or_docs for file in files):
        return "docs/config updates"
    if len(modules) == 1:
        mod = next(iter(modules))
        return "root-level changes" if mod == "__root__" else f"{mod} changes"
    return "cross-module changes"

"""Presentation: terminal text reporter with ANSI colors."""

from __future__ import annotations

from src.domain.entity.proposed_pr import ProposedPR
from src.domain.service.merge_order_resolver import compute_merge_order, compute_waves

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
DIM = "\033[2m"


def print_analysis(prs, branch, base, total_files, graph):
    _print_header(branch, base, total_files, len(prs), graph)
    for pr in prs:
        _print_pr(pr)
    _print_merge_order(prs)
    _print_waves(prs)
    _print_legend()


def _print_header(branch, base, total_files, pr_count, graph):
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  Stacked PR Analysis{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")
    print(f"  Branch : {CYAN}{branch}{RESET}")
    print(f"  Base   : {CYAN}{base}{RESET}")
    print(f"  Files  : {total_files}")
    print(f"  PRs    : {GREEN}{pr_count}{RESET}")
    print(f"  Edges  : {graph.number_of_edges()} file-level")
    print(f"{BOLD}{'=' * 70}{RESET}")


def _print_pr(pr):
    rc = _risk_color(pr.risk_score)
    print(f"\n  {BOLD}{pr.title}{RESET}  {rc}risk={pr.risk_score}{RESET}")
    print(f"  {DIM}{'─' * 60}{RESET}")
    if pr.depends_on:
        deps = ", ".join(f"PR #{d}" for d in pr.depends_on)
        print(f"    Depends on : {YELLOW}{deps}{RESET}")
    else:
        print(f"    Depends on : {DIM}(none){RESET}")
    print(f"    Strategy   : {GREEN}{pr.merge_strategy}{RESET}")
    print(f"    {DIM}{pr.description}{RESET}")
    print(f"    Code: {pr.total_code_lines}  Total: {pr.total_all_lines}  Cx: {pr.total_complexity}")
    print(f"    Files ({len(pr.files)}):")
    for f in pr.files:
        cx = f" cx={f.cyclomatic_complexity}" if f.cyclomatic_complexity else ""
        doc = f" {DIM}(docs){RESET}" if f.is_text_or_docs else ""
        print(f"      [{f.status}] {f.path}  (+{f.added}/-{f.removed}){cx}{doc}")


def _print_merge_order(prs):
    print(f"\n  {BOLD}Merge order:{RESET}")
    print(f"  {DIM}{'─' * 60}{RESET}")
    for i, pr in enumerate(compute_merge_order(prs), 1):
        deps = f"  (after {', '.join(f'#{d}' for d in pr.depends_on)})" if pr.depends_on else ""
        rc = _risk_color(pr.risk_score)
        print(f"  {i}. {pr.title}  [{pr.merge_strategy}] {rc}risk={pr.risk_score}{RESET}{deps}")


def _print_waves(prs):
    waves = compute_waves(prs)
    print(f"\n  {BOLD}Parallelism:{RESET}")
    print(f"  {DIM}{'─' * 60}{RESET}")
    for i, wave in enumerate(waves, 1):
        names = ", ".join(f"PR #{pr.index}" for pr in wave)
        parallel = " (parallel)" if len(wave) > 1 else ""
        print(f"  Wave {i}: {names}{parallel}")


def _print_legend():
    print(f"\n  {BOLD}Strategy:{RESET}")
    print(f"  {GREEN}squash{RESET} — clean single commit")
    print(f"  {YELLOW}merge{RESET}  — has dependents / high complexity")
    print(f"  {CYAN}rebase{RESET} — docs only, linear history")
    print()


def _risk_color(score):
    if score < 0.3:
        return GREEN
    if score < 0.6:
        return YELLOW
    return RED

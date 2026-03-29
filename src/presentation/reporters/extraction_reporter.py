"""Presentation: extraction plan reporter."""

from __future__ import annotations

from src.application.extract_files import ExtractionResult

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"


def print_extraction(result: ExtractionResult) -> None:
    print(f"\n{BOLD}  Extraction Plan{RESET}")
    print(f'  Prompt : {CYAN}"{result.prompt}"{RESET}')
    print(f"  Branch : {GREEN}{result.branch_name}{RESET}")

    if result.rules:
        print(f"\n  {BOLD}Rules:{RESET}")
        for r in result.rules:
            print(f"    [{r.kind:12s}] {r.pattern}")

    print(f"\n  {BOLD}Matched ({len(result.matched_files)}):{RESET}")
    for f in result.matched_files:
        print(f"    [{f.status}] {f.path}  (+{f.added}/-{f.removed})")

    if result.dep_files:
        print(f"\n  {BOLD}Dependencies ({len(result.dep_files)}):{RESET}")
        for f in result.dep_files:
            print(f"    [{f.status}] {f.path}  {DIM}(dep){RESET}")

    print(f"\n  {BOLD}Commands:{RESET}")
    for cmd in result.commands:
        print(f"  {cmd}")
    print()

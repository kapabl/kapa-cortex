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
        for rule in result.rules:
            print(f"    [{rule.kind:12s}] {rule.pattern}")

    print(f"\n  {BOLD}Matched ({len(result.matched_files)}):{RESET}")
    for file in result.matched_files:
        print(f"    [{file.status}] {file.path}  (+{file.added}/-{file.removed})")

    if result.dep_files:
        print(f"\n  {BOLD}Dependencies ({len(result.dep_files)}):{RESET}")
        for file in result.dep_files:
            print(f"    [{file.status}] {file.path}  {DIM}(dep){RESET}")

    print(f"\n  {BOLD}Commands:{RESET}")
    for cmd in result.commands:
        print(f"  {cmd}")
    print()

"""Interface: CLI entry point. No business logic here."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.infrastructure.git.git_client import GitClient
from src.infrastructure.git.command_executor import ShellCommandRunner
from src.infrastructure.parsers.multi_lang_parser import MultiLangImportParser, MultiLangSymbolExtractor
from src.infrastructure.complexity.cached_analyzer import CachedComplexityAnalyzer
from src.infrastructure.llm.ollama_backend import OllamaLLMService, NullLLMService, check_llm_backends
from src.infrastructure.llm.llm_text_generator import LlmTextGenerator
from src.infrastructure.llm.rule_based_generator import RuleBasedGenerator
from src.infrastructure.persistence.json_plan_store import JsonPlanStore
from src.infrastructure.git.cochange_adapter import CachedCochangeProvider
from src.infrastructure.diff.difftastic_classifier import DifftasticClassifier

from src.application.analyze_branch import AnalyzeBranchUseCase
from src.application.extract_files import ExtractFilesUseCase
from src.application.generate_plan import GeneratePlanUseCase
from src.application.execute_plan import ExecutePlanUseCase

from src.interface.reporters.text_reporter import print_analysis
from src.interface.reporters.json_reporter import print_json
from src.interface.reporters.dot_reporter import generate_dot
from src.interface.reporters.plan_reporter import print_plan_status, print_commands, generate_shell_script
from src.interface.reporters.extraction_reporter import print_extraction

BOLD = "\033[0m\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


def main() -> None:
    args = _parse_args()
    args.func(args)
    sys.exit(0)


# ── Subcommand handlers ──────────────────────────────────────────────────


def _cmd_init(args):
    """Interactive setup for the current branch."""
    import json

    git = GitClient()
    branch = git.current_branch()
    base = git.detect_base()

    print(f"\n{BOLD}  kapa-cortex — initializing for branch {CYAN}{branch}{RESET}\n")

    base_input = input(f"  Base branch [{base}]: ").strip()
    if base_input:
        base = base_input

    max_files_input = input(f"  Approximate files per PR [3]: ").strip()
    max_files = int(max_files_input) if max_files_input else 3

    max_lines_input = input(f"  Approximate code lines per PR [200]: ").strip()
    max_lines = int(max_lines_input) if max_lines_input else 200

    config = {
        "branch": branch,
        "base": base,
        "max_files": max_files,
        "max_lines": max_lines,
    }

    config_dir = Path(".cortex-cache/branches") / branch.replace("/", "-")
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))

    print(f"\n  {GREEN}Config saved to {config_path}{RESET}")
    print(f"  These are soft targets — the partitioner respects dependency")
    print(f"  constraints and test pairing even if it exceeds these limits.\n")
    print(f"  Next: {CYAN}kapa-cortex analyze{RESET}")


def _cmd_setup(args):
    """Install all dependencies and configure."""
    from src.infrastructure.setup import run_full_setup
    success = run_full_setup(ollama_model=args.ai_model, minimal=args.minimal)
    sys.exit(0 if success else 1)


def _cmd_index(args):
    """Index the repository using the Rust engine."""
    import subprocess
    subprocess.run(["kapa-cortex-core", "index", "."])


def _cmd_reindex(args):
    """Re-index specific files or all files via daemon."""
    from src.interface.daemon.client import send_query

    _ensure_daemon()
    files = args.files if args.files else None
    response = send_query("reindex", {"files": files})
    if response.status != "ok":
        print(f"  {RED}{response.error}{RESET}")
        sys.exit(1)
    count = response.data.get("reindexed", 0)
    print(f"  {GREEN}✓{RESET} Reindexed {count} files")


def _cmd_lookup(args):
    """Find all definitions of a symbol across all scopes."""
    import json as json_mod

    _ensure_daemon()
    data = _query_or_local("lookup", {"target": args.symbol})

    if args.json:
        print(json_mod.dumps(data, indent=2))
        return

    defs = data.get("definitions", [])
    if not defs:
        print(f"  {RED}No definitions found for: {args.symbol}{RESET}")
        sys.exit(1)

    print(f"  {BOLD}{args.symbol}{RESET} ({len(defs)} definitions):")
    for defn in defs:
        fqn = defn.get("fqn", args.symbol)
        kind = defn.get("kind", "")
        file_path = defn.get("file", "")
        line = defn.get("line", 0)
        print(f"    {fqn}  {DIM}{kind}  {file_path}:{line}{RESET}")


def _cmd_refs(args):
    """Find all references to symbols via LSP."""
    import json as json_mod

    _ensure_daemon()
    fqn_list = args.fqn
    if len(fqn_list) == 1:
        data = _query_or_local("refs", {"target": fqn_list[0]})
    else:
        data = _query_or_local("refs", {"targets": fqn_list})

    if args.json:
        print(json_mod.dumps(data, indent=2))
        return

    if data.get("query") == "refs_batch":
        for result in data.get("results", []):
            _print_refs_result(result)
            print()
    else:
        _print_refs_result(data)


def _print_refs_result(data: dict) -> None:
    """Print a single refs result."""
    if "error" in data:
        print(f"  {RED}{data['fqn']}: {data['error']}{RESET}")
        return
    refs = data.get("references", [])
    fqn = data.get("fqn", "")
    source_file = data.get("file", "")
    source_line = data.get("line", 0)
    print(f"  {BOLD}{fqn}{RESET}  {DIM}defined at {source_file}:{source_line}{RESET}")
    print(f"  {len(refs)} references:")
    for ref in refs:
        print(f"    {ref['file']}:{ref['line']}")


def _cmd_explain(args):
    """Compact summary of a symbol: definition, callers, callees, overrides."""
    import json as json_mod

    _ensure_daemon()
    data = _query_or_local("explain", {"target": args.fqn})

    if args.json:
        print(json_mod.dumps(data, indent=2))
        return

    fqn = data.get("fqn", args.fqn)
    sig = data.get("signature", "")
    source_file = data.get("file", "")
    source_line = data.get("line", 0)
    callers = data.get("callers", [])
    callees = data.get("callees", [])
    overrides = data.get("overrides", [])

    print(f"  {BOLD}{fqn}{RESET}")
    print(f"  {DIM}{sig}{RESET}")
    print(f"  {DIM}{source_file}:{source_line}{RESET}")
    print()

    if callers:
        print(f"  {BOLD}callers{RESET} ({len(callers)}):")
        for caller in callers:
            print(f"    {caller['function']}  {DIM}{caller['file']}:{caller['line']}{RESET}")
    else:
        print(f"  {BOLD}callers{RESET}: {DIM}none in index{RESET}")

    if callees:
        print(f"  {BOLD}callees{RESET} ({len(callees)}):")
        for callee in callees:
            print(f"    {callee['function']}  {DIM}{callee['file']}:{callee['line']}{RESET}")
    else:
        print(f"  {BOLD}callees{RESET}: {DIM}none in index{RESET}")

    if overrides:
        print(f"  {BOLD}overrides{RESET} ({len(overrides)}):")
        for override in overrides:
            print(f"    {override['fqn']}  {DIM}{override['file']}:{override['line']}{RESET}")


def _query_or_local(action: str, params: dict) -> dict:
    """Route query through Rust daemon (starting it if needed)."""
    from src.interface.daemon.client import send_query

    _ensure_daemon()
    response = send_query(action, params)
    if response.status != "ok":
        print(f"  {RED}{response.error}{RESET}")
        sys.exit(1)
    return response.data


def _cmd_impact(args):
    """What breaks if this file or symbol changes."""
    import json as json_mod

    target = getattr(args, "file", None)

    if not args.symbol and not target:
        print(f"  {RED}Provide a file or --symbol NAME{RESET}")
        sys.exit(1)

    if args.symbol:
        data = _query_or_local("symbol_impact_full", {"target": args.symbol})
        if args.json:
            print(json_mod.dumps(data, indent=2))
        else:
            _print_full_impact(data, args)
    else:
        data = _query_or_local("impact", {"target": target})
        if args.json:
            print(json_mod.dumps(data, indent=2))
        else:
            _print_file_impact(data)


def _print_symbol_impact(data: dict) -> None:
    """Print symbol impact as an indented call chain."""
    symbol = data.get("symbol", "")
    target_file = data.get("file", "")
    chains = data.get("call_chains", [])
    affected_files = data.get("affected_files", [])

    print(f"\n  {BOLD}Impact of {CYAN}{symbol}{RESET}" +
          (f" ({target_file})" if target_file else "") + ":")
    if chains:
        print(f"  Call chain ({len(chains)} calls, {len(affected_files)} files):")
        for chain in chains:
            caller = chain.get("caller_function", "")
            caller_file = chain.get("caller_file", "")
            callee = chain.get("callee_function", "")
            line = chain.get("line", 0)
            depth = chain.get("depth", 0)
            indent = "  " * depth
            print(f"    {indent}{caller}() → {callee}()  {DIM}{caller_file}:{line}{RESET}")
    if not chains:
        print(f"  {DIM}No callers found.{RESET}")
    print()


def _print_file_impact(data: dict) -> None:
    """Print file impact results from daemon."""
    target = data.get("target", "")
    direct = data.get("direct", [])
    transitive = data.get("transitive", [])
    total = data.get("total_affected", 0)

    print(f"\n  {BOLD}Impact of {CYAN}{target}{RESET}:")
    if direct:
        print(f"  Direct ({len(direct)}):")
        for path in direct:
            print(f"    {path}")
    if transitive:
        print(f"  Transitive ({len(transitive)}):")
        for path in transitive:
            print(f"    {path}")
    print(f"\n  Total affected: {total}")
    print()


def _print_full_impact(data: dict, args) -> None:
    """Print unified impact — filters by --calls, --files, --refs or shows all."""
    symbol = data.get("symbol", "")
    target_file = data.get("file", "")
    calls = data.get("calls", [])
    file_deps = data.get("file_deps", {})
    lsp_refs = data.get("lsp_refs", [])
    lsp_status = data.get("lsp_status", "unavailable")

    show_all = not args.calls and not args.files and not args.refs

    print(f"\n  {BOLD}Impact of {CYAN}{symbol}{RESET}" +
          (f" ({target_file})" if target_file else "") + ":")

    # Call graph section
    if show_all or args.calls:
        if calls:
            affected_files = sorted({chain["caller_file"] for chain in calls})
            print(f"  {BOLD}Calls{RESET} ({len(calls)} calls, {len(affected_files)} files):")
            for chain in calls:
                caller = chain.get("caller_function", "")
                caller_file = chain.get("caller_file", "")
                callee = chain.get("callee_function", "")
                line = chain.get("line", 0)
                depth = chain.get("depth", 0)
                indent = "  " * depth
                print(f"    {indent}{caller}() → {callee}()  {DIM}{caller_file}:{line}{RESET}")
        elif show_all:
            print(f"  {BOLD}Calls{RESET}: {DIM}none{RESET}")

    # File deps section
    if show_all or args.files:
        direct = file_deps.get("direct", [])
        transitive = file_deps.get("transitive", [])
        total = file_deps.get("total", 0)
        if direct or transitive:
            print(f"  {BOLD}File deps{RESET} ({total} affected):")
            for path in direct:
                print(f"    {path}  {DIM}direct{RESET}")
            for path in transitive:
                print(f"    {path}  {DIM}transitive{RESET}")
        elif show_all:
            print(f"  {BOLD}File deps{RESET}: {DIM}none{RESET}")

    # LSP refs section — grouped by file
    if show_all or args.refs:
        if lsp_refs:
            print(f"  {BOLD}References{RESET} ({len(lsp_refs)}):")
            _print_refs_grouped(lsp_refs)
        elif lsp_status == "ready":
            print(f"  {BOLD}References{RESET}: {DIM}none{RESET}")
        elif lsp_status == "unavailable":
            print(f"  {BOLD}References{RESET}: {DIM}no LSP server{RESET}")

    print()


def _print_refs_grouped(refs: list[dict]) -> None:
    """Print references grouped by file with source lines and kind."""
    from collections import defaultdict

    by_file: dict[str, list[dict]] = defaultdict(list)
    for ref in refs:
        by_file[ref["file"]].append(ref)

    for file_path in sorted(by_file.keys()):
        file_refs = by_file[file_path]
        short_path = file_path.rsplit("/", 1)[-1]
        print(f"    {BOLD}{file_path}{RESET} ({len(file_refs)}):")
        for ref in sorted(file_refs, key=lambda r: r["line"]):
            line = ref["line"]
            source = ref.get("source", "")
            kind = ref.get("kind", "ref")
            # Truncate long lines
            if len(source) > 80:
                source = source[:77] + "..."
            print(f"      {line:4d}: {source}  {DIM}←{kind}{RESET}")


def _cmd_hotspots(args):
    """Rank files by complexity × dependents."""
    import json as json_mod

    data = _query_or_local("hotspots", {"limit": args.limit})

    if args.json:
        print(json_mod.dumps(data, indent=2))
    else:
        hotspots = data if isinstance(data, list) else data.get("hotspots", [])
        print(f"\n  {BOLD}Hotspots (complexity × dependents):{RESET}")
        for index, entry in enumerate(hotspots, 1):
            print(f"  {index:3d}. {entry['path']}  cx={entry['complexity']}  dependents={entry['dependents']}  score={entry['score']:.0f}")
        print()


def _cmd_deps(args):
    """Show forward dependencies of a file."""
    import json as json_mod

    data = _query_or_local("deps", {"target": args.file})

    if args.json:
        print(json_mod.dumps(data, indent=2))
    else:
        deps = data.get("dependencies", [])
        print(f"\n  {BOLD}Dependencies of {CYAN}{args.file}{RESET}:")
        for path in deps:
            print(f"    {path}")
        print(f"\n  Total: {len(deps)}")
        print()


def _print_impact(result, use_json, json_mod):
    """Print impact analysis result."""
    if use_json:
        print(json_mod.dumps({
            "target": result.target,
            "direct": result.direct,
            "transitive": result.transitive,
            "total_affected": result.total_affected,
        }, indent=2))
    else:
        print(f"\n  {BOLD}Impact of {CYAN}{result.target}{RESET}:")
        if result.direct:
            print(f"  Direct ({len(result.direct)}):")
            for path in result.direct:
                print(f"    {path}")
        if result.transitive:
            print(f"  Transitive ({len(result.transitive)}):")
            for path in result.transitive:
                print(f"    {path}")
        print(f"\n  Total affected: {result.total_affected}")
        if result.total_affected == 0:
            print(f"  {DIM}No files depend on this file.{RESET}")
        print()


def _cmd_analyze(args):
    """Analyze branch and propose stacked PRs."""
    _apply_branch_config(args)
    git = GitClient()
    if args.base is None:
        args.base = git.detect_base()

    llm = _build_llm(args)
    analysis = _run_analysis(args, git, llm)

    if not analysis.files:
        print("No changes found.")
        sys.exit(0)

    if args.json:
        print_json(analysis.prs, args.base, analysis.branch, analysis.graph)
    elif args.dot:
        dot = generate_dot(analysis.prs)
        print(dot)
    else:
        print_analysis(analysis.prs, analysis.branch, args.base, len(analysis.files), analysis.graph)


def _cmd_plan(args):
    """Generate execution plan with git commands."""
    _apply_branch_config(args)
    git = GitClient()
    if args.base is None:
        args.base = git.detect_base()

    llm = _build_llm(args)
    analysis = _run_analysis(args, git, llm)

    if not analysis.files:
        print("No changes found.")
        sys.exit(0)

    text_generator = _build_text_generator(llm)
    plan_use_case = GeneratePlanUseCase(text_generator)
    plan = plan_use_case.execute(
        analysis.prs, analysis.branch, args.base,
        create_github_prs=not args.no_gh,
    )
    store = JsonPlanStore(args.plan_file)
    store.save(plan)
    print(f"Plan saved to {args.plan_file}", file=sys.stderr)

    if args.shell_script:
        print(generate_shell_script(plan))
    elif args.commands:
        print_commands(plan)
    else:
        print_analysis(analysis.prs, analysis.branch, args.base, len(analysis.files), analysis.graph)
        print_commands(plan)


def _cmd_run(args):
    """Execute a generated plan."""
    store = JsonPlanStore(args.plan_file)
    plan = store.load()
    if not plan:
        print(f"  {RED}No plan found. Run: kapa-cortex plan{RESET}")
        sys.exit(1)

    runner = ShellCommandRunner()
    execute_use_case = ExecutePlanUseCase(runner, store)
    success = execute_use_case.execute(plan, step_id=args.step, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


def _cmd_status(args):
    """Show plan progress."""
    store = JsonPlanStore(args.plan_file)
    plan = store.load()
    if not plan:
        print(f"  {RED}No plan found. Run: kapa-cortex plan{RESET}")
        sys.exit(1)
    print_plan_status(plan)


def _cmd_extract(args):
    """Extract a subset of changes into a PR branch."""
    git = GitClient()
    if args.base is None:
        args.base = git.detect_base()

    llm = _build_llm(args)
    result = _run_extraction(args, git, llm)
    print_extraction(result)
    if not result.all_files:
        print(f"  {YELLOW}No files matched. Try a different query.{RESET}")
        sys.exit(1)


def _cmd_daemon(args):
    """Manage the daemon."""
    if args.daemon_action == "start":
        _start_daemon()
    elif args.daemon_action == "stop":
        _stop_daemon()
    elif args.daemon_action == "status":
        _print_daemon_status()


def _cmd_install_skill(args):
    """Install Claude Code skill."""
    _install_claude_skill()


def _cmd_ai_check(args):
    """Check LLM backend status."""
    _print_ai_status()


# ── Argument parser ──────────────────────────────────────────────────────


def _parse_args():
    root = argparse.ArgumentParser(
        prog="kapa-cortex",
        description="Local code intelligence engine — stacked PRs, repo analysis, dependency graphs.",
    )
    root.add_argument("--no-ai", action="store_true", help="Disable local LLM")
    root.add_argument("--ai-backend", type=str, choices=["ollama", "llama-cpp", "none"])
    root.add_argument("--ai-model", type=str)

    subparsers = root.add_subparsers(dest="command")

    # ── init ──
    init_parser = subparsers.add_parser("init", help="Interactive setup for current branch")
    init_parser.set_defaults(func=_cmd_init)

    # ── setup ──
    setup_parser = subparsers.add_parser("setup", help="Install all dependencies")
    setup_parser.add_argument("--minimal", action="store_true", help="Smallest LLM model")
    setup_parser.set_defaults(func=_cmd_setup)

    # ── index ──
    index_parser = subparsers.add_parser("index", help="Pre-compute caches")
    index_parser.set_defaults(func=_cmd_index)

    # ── reindex ──
    reindex_parser = subparsers.add_parser("reindex", help="Re-index files via daemon")
    reindex_parser.add_argument("files", nargs="*", help="Files to re-index (all if omitted)")
    reindex_parser.set_defaults(func=_cmd_reindex)

    # ── impact ──
    impact_parser = subparsers.add_parser("impact", help="What breaks if this changes")
    impact_parser.add_argument("file", nargs="?", help="File to analyze (file-to-file impact)")
    impact_parser.add_argument("--symbol", type=str, metavar="NAME", help="Symbol to analyze")
    impact_parser.add_argument("--calls", action="store_true", help="Show only call chains")
    impact_parser.add_argument("--files", action="store_true", help="Show only file dependencies")
    impact_parser.add_argument("--refs", action="store_true", help="Show only type/reference usage")
    impact_parser.add_argument("--json", action="store_true", help="JSON output")
    impact_parser.set_defaults(func=_cmd_impact)

    # ── lookup ──
    lookup_parser = subparsers.add_parser("lookup", help="Find all definitions of a symbol")
    lookup_parser.add_argument("symbol", help="Symbol name to look up")
    lookup_parser.add_argument("--json", action="store_true", help="JSON output")
    lookup_parser.set_defaults(func=_cmd_lookup)

    # ── refs ──
    refs_parser = subparsers.add_parser("refs", help="Find all references to a symbol (LSP)")
    refs_parser.add_argument("fqn", nargs="+", help="Fully qualified name(s) (e.g. Class::method)")
    refs_parser.add_argument("--json", action="store_true", help="JSON output")
    refs_parser.set_defaults(func=_cmd_refs)

    # ── explain ──
    explain_parser = subparsers.add_parser("explain", help="Compact symbol summary")
    explain_parser.add_argument("fqn", help="Fully qualified name (e.g. Class::method)")
    explain_parser.add_argument("--json", action="store_true", help="JSON output")
    explain_parser.set_defaults(func=_cmd_explain)

    # ── hotspots ──
    hotspots_parser = subparsers.add_parser("hotspots", help="Rank files by complexity × dependents")
    hotspots_parser.add_argument("--limit", type=int, default=20, help="Max results")
    hotspots_parser.add_argument("--json", action="store_true", help="JSON output")
    hotspots_parser.set_defaults(func=_cmd_hotspots)

    # ── deps ──
    deps_parser = subparsers.add_parser("deps", help="Show forward dependencies of a file")
    deps_parser.add_argument("file", help="File to analyze")
    deps_parser.add_argument("--json", action="store_true", help="JSON output")
    deps_parser.set_defaults(func=_cmd_deps)

    # ── analyze ──
    analyze_parser = subparsers.add_parser("analyze", help="Analyze branch, propose stacked PRs")
    analyze_parser.add_argument("--base", default=None)
    analyze_parser.add_argument("--max-files", type=int, default=3)
    analyze_parser.add_argument("--max-lines", type=int, default=200)
    analyze_parser.add_argument("--json", action="store_true", help="JSON output")
    analyze_parser.add_argument("--dot", action="store_true", help="DOT graph output")
    analyze_parser.set_defaults(func=_cmd_analyze)

    # ── plan ──
    plan_parser = subparsers.add_parser("plan", help="Generate execution plan")
    plan_parser.add_argument("--base", default=None)
    plan_parser.add_argument("--max-files", type=int, default=3)
    plan_parser.add_argument("--max-lines", type=int, default=200)
    plan_parser.add_argument("--plan-file", default=".cortex-plan.json")
    plan_parser.add_argument("--no-gh", action="store_true", help="Skip GitHub PR creation")
    plan_parser.add_argument("--commands", action="store_true", help="Print git commands only")
    plan_parser.add_argument("--shell-script", action="store_true", help="Output as bash script")
    plan_parser.set_defaults(func=_cmd_plan)

    # ── run ──
    run_parser = subparsers.add_parser("run", help="Execute a generated plan")
    run_parser.add_argument("--plan-file", default=".cortex-plan.json")
    run_parser.add_argument("--step", type=int, default=None, help="Execute single step")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    run_parser.set_defaults(func=_cmd_run)

    # ── status ──
    status_parser = subparsers.add_parser("status", help="Show plan progress")
    status_parser.add_argument("--plan-file", default=".cortex-plan.json")
    status_parser.set_defaults(func=_cmd_status)

    # ── extract ──
    extract_parser = subparsers.add_parser("extract", help="Extract file subset into PR branch")
    extract_parser.add_argument("prompt", help="Natural language description")
    extract_parser.add_argument("--base", default=None)
    extract_parser.add_argument("--branch", type=str, dest="extract_branch")
    extract_parser.add_argument("--no-deps", action="store_true")
    extract_parser.set_defaults(func=_cmd_extract)

    # ── daemon ──
    daemon_parser = subparsers.add_parser("daemon", help="Manage daemon (start/stop/status)")
    daemon_parser.add_argument("daemon_action", choices=["start", "stop", "status"])
    daemon_parser.set_defaults(func=_cmd_daemon)

    # ── install-skill ──
    skill_parser = subparsers.add_parser("install-skill", help="Install Claude Code skill")
    skill_parser.set_defaults(func=_cmd_install_skill)

    # ── ai-check ──
    ai_parser = subparsers.add_parser("ai-check", help="Check LLM backend status")
    ai_parser.set_defaults(func=_cmd_ai_check)

    args = root.parse_args()
    if not hasattr(args, "func"):
        root.print_help()
        sys.exit(0)

    return args


# ── Shared helpers ───────────────────────────────────────────────────────


def _apply_branch_config(args):
    """Load branch config from init and apply as defaults."""
    import json

    git = GitClient()
    branch = git.current_branch()
    config_path = Path(".cortex-cache/branches") / branch.replace("/", "-") / "config.json"

    if not config_path.exists():
        return

    config = json.loads(config_path.read_text())

    if getattr(args, "base", None) is None:
        args.base = config.get("base")
    if getattr(args, "max_files", None) == 3:  # still at default
        args.max_files = config.get("max_files", 3)
    if getattr(args, "max_lines", None) == 200:  # still at default
        args.max_lines = config.get("max_lines", 200)


def _build_llm(args):
    if getattr(args, "no_ai", False) or getattr(args, "ai_backend", None) == "none":
        return NullLLMService()
    return OllamaLLMService(
        backend=getattr(args, "ai_backend", None),
        model=getattr(args, "ai_model", None),
    )


def _build_text_generator(llm):
    if llm.available:
        return LlmTextGenerator(llm)
    return RuleBasedGenerator()


def _run_analysis(args, git, llm):
    parser = MultiLangImportParser()
    symbols = MultiLangSymbolExtractor()
    complexity = CachedComplexityAnalyzer()
    cochange = CachedCochangeProvider()
    diff_classifier = DifftasticClassifier()
    text_generator = _build_text_generator(llm)
    analyze_use_case = AnalyzeBranchUseCase(
        git, parser, symbols, complexity,
        cochange, diff_classifier, text_generator,
    )
    print(f"Analyzing...", file=sys.stderr)
    return analyze_use_case.execute(args.base, args.max_files, args.max_lines)


def _run_extraction(args, git, llm):
    base_ref = git.resolve_base(args.base)
    files = git.diff_stat(base_ref)
    parser = MultiLangImportParser()

    import networkx as nx
    from src.domain.service.dependency_resolver import build_dependency_edges
    imports_by_file = {}
    for file in files:
        source = git.file_source(file.path)
        if source:
            imports_by_file[file.path] = parser.parse(file.path, source)
    edges = build_dependency_edges(files, imports_by_file)
    dep_graph = nx.DiGraph()
    for file in files:
        dep_graph.add_node(file.path)
    for src, dst, _, _ in edges:
        dep_graph.add_edge(src, dst)

    extract_use_case = ExtractFilesUseCase(llm)
    return extract_use_case.execute(
        prompt=args.prompt, all_files=files, graph=dep_graph,
        source_branch=git.current_branch(), base_branch=args.base,
        branch_name=getattr(args, "extract_branch", None),
        include_deps=not args.no_deps,
    )


def _install_claude_skill():
    import shutil

    skill_source = Path(__file__).resolve().parent.parent / "skill"
    skill_target = Path.home() / ".claude" / "skills" / "kapa-cortex"

    if not skill_source.exists():
        print(f"  {RED}Skill source not found at {skill_source}{RESET}")
        print(f"  {RED}kapa-cortex may not be installed correctly.{RESET}")
        sys.exit(1)

    if skill_target.exists():
        shutil.rmtree(skill_target)

    shutil.copytree(skill_source, skill_target)
    print(f"  {GREEN}Skill installed to {skill_target}{RESET}")
    print(f"  Claude Code will auto-trigger on phrases like:")
    print(f"    {CYAN}\"split this branch into PRs\"{RESET}")
    print(f"    {CYAN}\"analyze my changes\"{RESET}")
    print(f"    {CYAN}\"what depends on this file\"{RESET}")
    print(f"  Or invoke directly: {CYAN}/kapa-cortex{RESET}")


def _ensure_daemon():
    """Make sure the Rust daemon is running. Start it if needed."""
    from src.interface.daemon.client import is_daemon_running

    if is_daemon_running():
        return

    import subprocess
    import time as _time
    import os as _os

    SOCKET_PATH = "/tmp/kapa-cortex.sock"
    RUST_BINARY = "kapa-cortex-core"

    proc = subprocess.Popen(
        [RUST_BINARY, "daemon", "start"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )

    for _ in range(300):
        if _os.path.exists(SOCKET_PATH):
            print(f"  {GREEN}Daemon started (pid {proc.pid}){RESET}", file=sys.stderr)
            return
        _time.sleep(0.1)
    print(f"  {YELLOW}Daemon started but socket not ready{RESET}", file=sys.stderr)


def _start_daemon():
    """Start the Rust daemon (foreground)."""
    import subprocess
    subprocess.run(["kapa-cortex-core", "daemon", "start"])


def _stop_daemon():
    """Stop the Rust daemon."""
    import subprocess
    subprocess.run(["kapa-cortex-core", "daemon", "stop"])


def _print_daemon_status():
    """Print Rust daemon status."""
    import subprocess
    subprocess.run(["kapa-cortex-core", "status"])




def _print_ai_status():
    results = check_llm_backends()
    print(f"\n{BOLD}  LLM Backends{RESET}")
    for name, info in results.items():
        avail = f"{GREEN}available{RESET}" if info.get("available") else f"{RED}unavailable{RESET}"
        print(f"  {name:12s}: {avail}")
        for key, value in info.items():
            if key == "available":
                continue
            if key == "models" and isinstance(value, list):
                print(f"    {key}: {', '.join(value[:10])}")
            else:
                print(f"    {key}: {value}")
    print(f"\n  AI is ON by default. Use {CYAN}--no-ai{RESET} to disable.")
    print(f"  Setup: {CYAN}kapa-cortex setup{RESET}")
    print()

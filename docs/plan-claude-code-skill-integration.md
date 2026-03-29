# Plan: kapa-cortex — Claude Code Skill + Code Intelligence Engine

## Context

kapa-cortex (renamed from kapa-stacker) is a local code intelligence engine that:
1. **Splits feature branches into stacked PRs** — dependency-aware, multi-language
2. **Analyzes entire repos** — full-repo indexing for monorepo code walks, migrations, impact analysis

Making it a Claude Code skill means Claude uses `kapa-cortex --json` output instead of reading raw source files — saving thousands of tokens per analysis. All heavy computation (tree-sitter, ast-grep, ctags, lizard, difftastic, co-change, LSP) runs locally on CPU.

## Phase 1: Rename kapa-stacker → kapa-cortex

### Why
"stacker" pigeonholes the tool into PR splitting. "cortex" captures both capabilities: local intelligence layer that understands code structure (analysis) and acts on it (PR splitting, merge strategies, repo analysis).

### Changes
- `pyproject.toml` — package name, CLI entry point, metadata
- `src/` — update all internal references
- `tests/` — update imports
- `CLAUDE.md` — update references
- `docs/session-summary.md` — update project name
- `.claude/` — update any references
- `kapa-stacker.py` → `kapa-cortex.py` (entry point script)

## Phase 2: Claude Code Skill

### Files to Create

```
.claude/skills/kapa-cortex/
├── SKILL.md                           # Core skill (triggers, workflow, token rules)
├── references/
│   ├── cli-reference.md               # Full CLI flags and options
│   ├── json-schema.md                 # --json and plan JSON schemas
│   └── advanced-workflows.md          # Extract, partial execution, visualization
└── scripts/
    └── check_cache_freshness.sh       # Exit 0 if cache fresh, 1 if stale
```

### SKILL.md Design (~1500 words)

**Frontmatter triggers:**
- "split this branch into PRs"
- "analyze my changes for PRs"
- "create stacked PRs"
- "extract files for a PR"
- "stack my branch"
- "analyze this repo"
- "what are the dependencies between these files"
- "show me the impact of this change"

**Body — 6 sections (imperative form):**

1. **Token-saving rule** — Never read source files for branch structure. Always `kapa-cortex --json` first. Tool does all analysis locally on CPU.

2. **Prerequisites** — Check `kapa-cortex` available, install if needed (`pip install -e .`), verify git repo.

3. **Core workflow:**
   - Check cache freshness → `kapa-cortex --index` if stale
   - `kapa-cortex --json` → parse structured output
   - Use JSON to answer questions (dependencies, grouping, risk)
   - `--generate-plan` for git commands
   - `--extract "description"` for subsets
   - `--run-plan --dry-run` then `--run-plan` with confirmation

4. **Flag reference** — Compact table of key flags

5. **JSON output schema** — Brief inline description of fields

6. **Safety rules** — Always dry-run first, warn on uncommitted changes, use `--check-plan` + `--step N` for retries

### References

**cli-reference.md** — All argparse flags with types, defaults, descriptions. AI backend options. Plan file format. Exit codes.

**json-schema.md** — `--json` output schema, plan JSON schema, field explanations (risk_score, merge_strategy, status codes).

**advanced-workflows.md** — Extraction, partial execution, custom bases, large branch tuning, visualization, CI integration, troubleshooting.

### Scripts

**check_cache_freshness.sh** — Compare git commit timestamp to `.stacker-cache/` mtime. Cross-platform. Exit 0 = fresh, 1 = stale.

## Phase 3: LSP via MCP Integration

### Architecture: Two-tier analysis

kapa-cortex becomes the **unified layer** that combines LSP (for general languages) with its own parsers (for build languages that have no LSP).

| Tier | Languages | Tool | Precision |
|------|-----------|------|-----------|
| **LSP via MCP** | Python, TypeScript, Go, Rust, Java, Kotlin, C/C++ | Existing MCP servers (cclsp, claude-code-lsps, mcp-language-server) | Exact (compiler-grade) |
| **kapa-cortex parsers** | Buck2, Bazel, Starlark, BXL, CMake, Gradle Groovy, Gradle KTS, Groovy | tree-sitter + ast-grep + regex | High (AST-level) |

### Why both tiers

Build system languages have **no LSP**:
- Buck2 — no LSP exists
- Bazel/Starlark — starlark-lsp (Stripe) is mostly dead
- BXL — no LSP exists
- CMake — cmake-language-server is basic, no cross-references
- Gradle — no real LSP
- Groovy — groovy-language-server is minimal

kapa-cortex is the **only tool that covers everything** because it doesn't depend solely on LSP.

### Existing MCP servers to consume

| Project | Scope |
|---------|-------|
| [claude-code-lsps](https://github.com/Piebald-AI/claude-code-lsps) | Claude Code plugin with 11 language LSP servers pre-packaged |
| [cclsp](https://github.com/ktnyt/cclsp) | MCP server built specifically for Claude Code + LSP (50ms vs 45s navigation) |
| [mcp-language-server](https://github.com/isaacphi/mcp-language-server) | Generic MCP→LSP bridge: go-to-definition, find-references, rename, diagnostics |

### Implementation

1. **New domain port:** `LspProvider` — interface for LSP operations (go-to-definition, find-references, call-hierarchy)
2. **New infrastructure adapter:** `McpLspAdapter` — calls MCP tools exposed by one of the existing servers
3. **Wire into dependency resolver:** For LSP-supported languages, use precise LSP edges. For build languages, fall back to kapa-cortex's own parsers.
4. **Configuration:** Let users configure which MCP LSP server to use (or auto-detect from `.claude/settings.json`)

### MCP tools to consume
```
lsp_goto_definition(file, line, column) → location
lsp_find_references(file, line, column) → locations[]
lsp_workspace_symbols(query) → symbols[]
lsp_call_hierarchy(file, line, column) → calls[]
lsp_diagnostics(file) → diagnostics[]
```

## Phase 4: Full-Repo Indexing

### Why
Current `--index` only helps analysis of changed files. For monorepo code walks, migrations, and impact analysis, we need full-repo indexing.

### Changes
- Expand `--index` to index **all** source files, not just changed ones
- Build a full dependency graph (all files, all imports, all symbols)
- Cache to `.cortex-cache/` (rename from `.stacker-cache/`)
- New CLI commands:
  - `kapa-cortex --impact "path/to/file.py"` — show all files affected by changes to this file
  - `kapa-cortex --deps "path/to/file.py"` — show full dependency chain
  - `kapa-cortex --hotspots` — files with highest complexity + most dependents
  - `kapa-cortex --migration-path "old_module" "new_module"` — trace migration impact

### JSON output for full-repo analysis
```json
{
  "repo_stats": { "files", "languages", "total_lines", "total_complexity" },
  "dependency_graph": { "nodes": [...], "edges": [...] },
  "hotspots": [...],
  "impact": { "direct": [...], "transitive": [...] }
}
```

## Critical Source Files
- `src/presentation/cli.py` — all CLI flags
- `src/presentation/reporters/json_reporter.py` — JSON output structure
- `src/domain/entity/execution_plan.py` — plan JSON schema
- `src/infrastructure/indexer/index_all.py` — cache details
- `src/application/extract_files.py` — extraction workflow
- `src/domain/service/dependency_resolver.py` — where LSP edges would feed in
- `src/infrastructure/parsers/import_dispatcher.py` — where LSP vs parser dispatch happens

## Implementation Order

1. **Rename** kapa-stacker → kapa-cortex (prerequisite for everything)
2. **Skill** — create `.claude/skills/kapa-cortex/` with SKILL.md and references
3. **LSP via MCP** — new port, adapter, wire into dependency resolver
4. **Full-repo indexing** — expand --index, add new CLI commands

## Verification
- `/kapa-cortex` in Claude Code — skill should load
- "analyze my changes" — skill should auto-trigger
- `kapa-cortex --json` output matches documented schema
- LSP edges appear in dependency graph for supported languages
- `kapa-cortex --index` indexes full repo
- `kapa-cortex --impact "file.py"` shows transitive dependents

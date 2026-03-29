# kapa-stacker

Split feature branches into reviewable, dependency-ordered stacked PRs.

Analyzes code dependencies across 15+ languages, groups files into small PRs
(~3 files, ~200 lines), generates git commands to create the branches, and
optionally uses a local LLM (ollama) for smarter grouping and PR descriptions.

## Install

```bash
pip install -e .

# Now use it anywhere:
kapa-stacker --help
```

Or without installing:

```bash
pip install -r requirements.txt
python kapa-stacker.py --help
```

## Quick Start

```bash
# Setup local LLM (optional — AI is on by default, falls back silently)
kapa-stacker --setup

# Analyze your branch and see proposed PRs
kapa-stacker --base main

# Generate an execution plan with all git commands
kapa-stacker --generate-plan

# Check plan progress
kapa-stacker --check-plan

# Execute the plan (interactive, with retry/skip)
kapa-stacker --run-plan

# Dry run (preview without executing)
kapa-stacker --run-plan --dry-run
```

## Extract Specific Changes

Pull a subset of files into a separate PR branch using natural language:

```bash
kapa-stacker --extract "gradle init-script files"
kapa-stacker --extract "src/core/ changes"
kapa-stacker --extract "all CMakeLists.txt changes"
kapa-stacker --extract "python test files"
kapa-stacker --extract "the authentication refactor"
```

## Output Formats

```bash
kapa-stacker --json
kapa-stacker --visualize
kapa-stacker --dot-file graph.dot
kapa-stacker --print-commands
kapa-stacker --shell-script > create-stack.sh
```

## AI Mode

AI is **on by default** using ollama. If ollama isn't running, it silently
falls back to rule-based analysis. No API keys needed.

```bash
kapa-stacker --setup              # install ollama + pull model
kapa-stacker --setup-minimal      # smallest model (~1.6 GB)
kapa-stacker --ai-check           # check status
kapa-stacker --no-ai              # disable AI
kapa-stacker --ai-model qwen2.5-coder:7b  # specific model
```

## Supported Languages

Python, C, C++, Java, Kotlin, Go, Rust, JavaScript, TypeScript,
Gradle (Groovy + KTS), CMake, Buck2, BXL, Starlark/Bazel, Groovy.

Import parsing uses a layered strategy: tree-sitter, ast-grep, Python ast,
universal-ctags, regex.

## Architecture (DDD + Layers)

```
src/
  domain/            # Core business logic, pure Python, zero external deps
    ports/           # Interfaces (GitReader, ImportParser, LLMService, etc.)
  application/       # Use cases (AnalyzeBranch, ExtractFiles, GeneratePlan)
  infrastructure/    # Git, parsers, LLM backends, persistence
  presentation/      # CLI, text/JSON/DOT/mermaid reporters
tests/
  domain/            # Fast, no-mock domain tests
  infrastructure/    # Integration tests
  application/       # Use case tests
  presentation/      # Output format tests
```

## Running Tests

```bash
# Domain tests (fast, pure logic, zero mocks)
python -m unittest discover -s tests/domain -v

# All tests
python -m unittest discover -s tests -v
```

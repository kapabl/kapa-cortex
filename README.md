# kapa-stacker

Split feature branches into reviewable, dependency-ordered stacked PRs.

Analyzes code dependencies across 15+ languages, groups files into small PRs
(~3 files, ~200 lines), generates git commands to create the branches, and
optionally uses a local LLM (ollama) for smarter grouping and PR descriptions.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Setup local LLM (optional but recommended — AI is on by default)
python -m src.presentation.cli --setup

# Analyze your branch and see proposed PRs
python -m src.presentation.cli --base main

# Generate an execution plan with all git commands
python -m src.presentation.cli --generate-plan

# Check plan progress
python -m src.presentation.cli --check-plan

# Execute the plan (interactive, with retry/skip)
python -m src.presentation.cli --run-plan

# Dry run (preview without executing)
python -m src.presentation.cli --run-plan --dry-run
```

## Extract Specific Changes

Pull a subset of files into a separate PR branch using natural language:

```bash
python -m src.presentation.cli --extract "gradle init-script files"
python -m src.presentation.cli --extract "src/core/ changes"
python -m src.presentation.cli --extract "all CMakeLists.txt changes"
python -m src.presentation.cli --extract "python test files"
python -m src.presentation.cli --extract "the authentication refactor"
```

## Output Formats

```bash
# JSON output
python -m src.presentation.cli --json

# Graphviz DOT
python -m src.presentation.cli --visualize
python -m src.presentation.cli --dot-file graph.dot

# Copy-pasteable git commands
python -m src.presentation.cli --print-commands

# Executable bash script
python -m src.presentation.cli --shell-script > create-stack.sh
```

## AI Mode

AI is **on by default** using ollama. If ollama isn't running, it silently
falls back to rule-based analysis. No API keys needed.

```bash
# First time setup (installs ollama, pulls model)
python -m src.presentation.cli --setup

# Use smallest model (~1.6 GB)
python -m src.presentation.cli --setup-minimal

# Check AI status
python -m src.presentation.cli --ai-check

# Disable AI explicitly
python -m src.presentation.cli --no-ai

# Force specific model
python -m src.presentation.cli --ai-model qwen2.5-coder:7b
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
# Domain tests (fast, pure logic)
python -m unittest discover -s tests/domain -v

# All tests
python -m unittest discover -s tests -v

# Legacy tests (still work)
python -m unittest test_analyzer -v
```

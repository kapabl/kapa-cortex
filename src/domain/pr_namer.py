"""Domain service: generate PR titles from actual code changes."""

from __future__ import annotations

from pathlib import Path

from src.domain.changed_file import ChangedFile


def generate_title(files: list[ChangedFile]) -> str:
    """
    Generate a PR title from the changes inside the files.

    Strategy (in priority order):
      1. New files with class/function defs → "Add {name}"
      2. Deleted files → "Remove {module}"
      3. Test-only → "Add tests for {module}"
      4. Single module → "Update {module}"
      5. Mixed → describe the dominant change
    """
    if not files:
        return "Empty PR"

    if _all_docs(files):
        return _docs_title(files)

    if _all_deleted(files):
        return _deletion_title(files)

    if _all_tests(files):
        return _test_title(files)

    new_symbols = _extract_new_symbols(files)
    if new_symbols:
        return _symbol_title(new_symbols, files)

    return _module_title(files)


def _all_docs(files: list[ChangedFile]) -> bool:
    return all(f.is_text_or_docs for f in files)


def _all_deleted(files: list[ChangedFile]) -> bool:
    return all(f.status == "D" for f in files)


def _all_tests(files: list[ChangedFile]) -> bool:
    test_indicators = {"test_", "_test.", ".test.", ".spec.", "Test."}
    return all(
        any(ind in f.path for ind in test_indicators)
        for f in files
    )


def _docs_title(files: list[ChangedFile]) -> str:
    names = [Path(f.path).stem for f in files[:2]]
    return f"Update {', '.join(names)} docs"


def _deletion_title(files: list[ChangedFile]) -> str:
    modules = _top_modules(files)
    return f"Remove {', '.join(modules)}"


def _test_title(files: list[ChangedFile]) -> str:
    modules = _top_modules(files)
    return f"Add tests for {', '.join(modules)}"


def _symbol_title(
    symbols: list[str],
    files: list[ChangedFile],
) -> str:
    verb = "Add" if _has_new_files(files) else "Update"
    top = symbols[:2]
    suffix = f" (+{len(symbols) - 2} more)" if len(symbols) > 2 else ""
    return f"{verb} {', '.join(top)}{suffix}"


def _module_title(files: list[ChangedFile]) -> str:
    modules = _top_modules(files)
    if len(modules) == 1:
        mod = modules[0]
        verb = "Add" if _has_new_files(files) else "Update"
        return f"{verb} {mod}"
    return f"Update {', '.join(modules[:2])}"


def _extract_new_symbols(files: list[ChangedFile]) -> list[str]:
    """Extract class/function names from added lines."""
    symbols: list[str] = []
    for f in files:
        for line in f.diff_text.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            clean = line[1:].strip()
            name = _parse_symbol_from_line(clean)
            if name and name not in symbols:
                symbols.append(name)
            if len(symbols) >= 3:
                return symbols
    return symbols


def _parse_symbol_from_line(line: str) -> str | None:
    """Try to extract a symbol name from a source line."""
    for prefix in ("class ", "def ", "func ", "fn ", "function ", "struct ", "enum ", "interface "):
        if line.startswith(prefix):
            rest = line[len(prefix):].split("(")[0].split(":")[0].split("{")[0].strip()
            if rest and rest.isidentifier():
                return rest
    return None


def _top_modules(files: list[ChangedFile]) -> list[str]:
    modules: list[str] = []
    for f in files:
        mod = f.module_key
        if mod == "__root__":
            mod = Path(f.path).stem
        if mod not in modules:
            modules.append(mod)
    return modules[:3]


def _has_new_files(files: list[ChangedFile]) -> bool:
    return any(f.status == "A" for f in files)

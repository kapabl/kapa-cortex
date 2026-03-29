"""Domain service: parse natural language into extraction rules."""

from __future__ import annotations

import re

from src.domain.extraction_rule import ExtractionRule

_KEYWORD_MAP: dict[str, list[ExtractionRule]] = {
    "gradle": [
        ExtractionRule("glob", "*.gradle", "Gradle Groovy files"),
        ExtractionRule("glob", "*.gradle.kts", "Gradle KTS files"),
        ExtractionRule("glob", "gradle/**", "Gradle wrapper/config"),
        ExtractionRule("glob", "gradlew*", "Gradle wrapper scripts"),
        ExtractionRule("glob", "buildSrc/**", "Gradle buildSrc"),
    ],
    "cmake": [
        ExtractionRule("glob", "CMakeLists.txt", "CMake list files"),
        ExtractionRule("glob", "*.cmake", "CMake modules"),
        ExtractionRule("glob", "cmake/**", "CMake directory"),
    ],
    "buck": [
        ExtractionRule("glob", "BUCK", "Buck2 build files"),
        ExtractionRule("glob", "TARGETS", "Buck2 target files"),
        ExtractionRule("glob", "*.bxl", "BXL extension files"),
    ],
    "buck2": [
        ExtractionRule("glob", "BUCK", "Buck2 build files"),
        ExtractionRule("glob", "TARGETS", "Buck2 target files"),
        ExtractionRule("glob", "*.bxl", "BXL extension files"),
    ],
    "starlark": [
        ExtractionRule("glob", "*.bzl", "Starlark files"),
        ExtractionRule("glob", "BUILD", "Bazel BUILD files"),
        ExtractionRule("glob", "BUILD.bazel", "Bazel BUILD files"),
    ],
    "bazel": [
        ExtractionRule("glob", "*.bzl", "Bazel Starlark files"),
        ExtractionRule("glob", "BUILD", "Bazel BUILD files"),
        ExtractionRule("glob", "BUILD.bazel", "Bazel BUILD files"),
        ExtractionRule("glob", "WORKSPACE*", "Bazel workspace"),
    ],
    "python": [
        ExtractionRule("ext", ".py", "Python source files"),
        ExtractionRule("ext", ".pyi", "Python type stubs"),
    ],
    "test": [
        ExtractionRule("glob", "**/test_*.py", "Python tests"),
        ExtractionRule("glob", "**/*_test.py", "Python tests"),
        ExtractionRule("glob", "**/*_test.go", "Go tests"),
        ExtractionRule("glob", "**/*.test.ts", "TS tests"),
        ExtractionRule("glob", "**/*.test.tsx", "TSX tests"),
        ExtractionRule("glob", "**/*Test.java", "Java tests"),
        ExtractionRule("glob", "**/*Test.kt", "Kotlin tests"),
        ExtractionRule("glob", "**/*_test.cpp", "C++ tests"),
    ],
    "docs": [
        ExtractionRule("ext", ".md", "Markdown"),
        ExtractionRule("ext", ".rst", "reStructuredText"),
        ExtractionRule("glob", "docs/**", "Docs directory"),
    ],
    "config": [
        ExtractionRule("ext", ".yaml", "YAML"),
        ExtractionRule("ext", ".yml", "YAML"),
        ExtractionRule("ext", ".toml", "TOML"),
        ExtractionRule("ext", ".json", "JSON"),
    ],
    "cpp": [
        ExtractionRule("ext", ".cpp", "C++ source"),
        ExtractionRule("ext", ".cc", "C++ source"),
        ExtractionRule("ext", ".h", "C/C++ headers"),
        ExtractionRule("ext", ".hpp", "C++ headers"),
    ],
    "java": [ExtractionRule("ext", ".java", "Java source")],
    "kotlin": [
        ExtractionRule("ext", ".kt", "Kotlin source"),
        ExtractionRule("ext", ".kts", "Kotlin script"),
    ],
}
_KEYWORD_MAP["tests"] = _KEYWORD_MAP["test"]
_KEYWORD_MAP["c++"] = _KEYWORD_MAP["cpp"]


def parse_prompt(prompt: str) -> list[ExtractionRule]:
    """Parse a natural-language prompt into matching rules."""
    rules: list[ExtractionRule] = []
    lower = prompt.lower().strip()

    _extract_globs(prompt, rules)
    _extract_path_prefixes(prompt, rules)
    _extract_filenames(prompt, rules)
    _extract_keywords(lower, rules)
    _extract_quoted_strings(prompt, rules)

    return _deduplicate(rules)


def _extract_globs(prompt: str, rules: list[ExtractionRule]) -> None:
    for m in re.finditer(r'([*?[\]{}]+[\w./\-*?]*|[\w./\-]+[*?[\]{}]+[\w./\-*?]*)', prompt):
        rules.append(ExtractionRule("glob", m.group(1), f"Glob: {m.group(1)}"))


def _extract_path_prefixes(prompt: str, rules: list[ExtractionRule]) -> None:
    for m in re.finditer(r'(?:^|\s)([\w\-]+(?:/[\w\-]+)*/)(?:\s|$)', prompt):
        rules.append(ExtractionRule("path_prefix", m.group(1), f"Path: {m.group(1)}"))


def _extract_filenames(prompt: str, rules: list[ExtractionRule]) -> None:
    glob_pat = re.compile(r'[*?[\]{}]')
    for m in re.finditer(r'(?:^|\s)([\w\-]+\.[\w.]+)(?:\s|$)', prompt):
        name = m.group(1)
        if not glob_pat.search(name):
            rules.append(ExtractionRule("glob", f"**/{name}", f"File: {name}"))


def _extract_keywords(lower: str, rules: list[ExtractionRule]) -> None:
    for keyword, keyword_rules in _KEYWORD_MAP.items():
        if keyword in lower:
            rules.extend(keyword_rules)


def _extract_quoted_strings(prompt: str, rules: list[ExtractionRule]) -> None:
    for m in re.finditer(r'["\']([^"\']+)["\']', prompt):
        rules.append(ExtractionRule("keyword", m.group(1), f"Keyword: {m.group(1)}"))


def _deduplicate(rules: list[ExtractionRule]) -> list[ExtractionRule]:
    seen: set[tuple[str, str]] = set()
    result: list[ExtractionRule] = []
    for r in rules:
        key = (r.kind, r.pattern)
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result

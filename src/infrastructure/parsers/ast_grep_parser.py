"""ast-grep based import extraction."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from src.domain.entity.import_ref import ImportRef

# ---------------------------------------------------------------------------
# Patterns per language: (ast-grep pattern, import kind)
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [
        ("import $MOD", "module"),
        ("from $MOD import $NAMES", "module"),
    ],
    "java": [
        ("import $MOD;", "package"),
        ("import static $MOD;", "package"),
    ],
    "kotlin": [
        ("import $MOD", "package"),
    ],
    "go": [
        ('import "$MOD"', "package"),
    ],
    "rust": [
        ("use $MOD;", "module"),
        ("use $MOD as $ALIAS;", "module"),
        ("mod $MOD;", "module"),
        ("extern crate $MOD;", "crate"),
    ],
    "c": [
        ('#include "$MOD"', "header"),
        ("#include <$MOD>", "header"),
    ],
    "cpp": [
        ('#include "$MOD"', "header"),
        ("#include <$MOD>", "header"),
    ],
    "typescript": [
        ("import $SPEC from '$MOD'", "module"),
        ('import $SPEC from "$MOD"', "module"),
        ("require('$MOD')", "module"),
        ('require("$MOD")', "module"),
    ],
    "javascript": [
        ("import $SPEC from '$MOD'", "module"),
        ('import $SPEC from "$MOD"', "module"),
        ("require('$MOD')", "module"),
        ('require("$MOD")', "module"),
    ],
}


def _normalize(raw: str, lang: str) -> str:
    cleaned = raw.strip("'\"<>")
    if lang in ("c", "cpp"):
        return cleaned.replace("/", ".").removesuffix(".h").removesuffix(".hpp").removesuffix(".hxx")
    if lang == "rust":
        return cleaned.replace("::", ".")
    if lang == "go":
        return cleaned
    return cleaned.replace("/", ".").replace("\\", ".")


def parse_imports(file_path: str, source: str, lang: str) -> list[ImportRef]:
    """Use ast-grep for pattern-based AST import extraction."""
    patterns = _PATTERNS.get(lang)
    if not patterns:
        return []

    suffix = Path(file_path).suffix or ".txt"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(source)
        tmp_path = f.name

    results: list[ImportRef] = []
    seen: set[str] = set()

    try:
        for pattern, kind in patterns:
            try:
                result = subprocess.run(
                    ["ast-grep", "--pattern", pattern,
                     "--lang", lang, "--json", tmp_path],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    continue

                for match in json.loads(result.stdout):
                    mod = _extract_module(match)
                    if mod and mod not in seen:
                        seen.add(mod)
                        results.append(ImportRef(
                            raw=mod,
                            module=_normalize(mod, lang),
                            kind=kind,
                        ))
            except (subprocess.TimeoutExpired, json.JSONDecodeError):
                continue
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return results


def _extract_module(match: dict) -> str:
    """Extract module name from an ast-grep match result."""
    meta = match.get("metaVariables", {})
    mod_node = meta.get("single", {}).get("MOD") or meta.get("MOD")
    if isinstance(mod_node, dict):
        return mod_node.get("text", "").strip("'\"")
    return match.get("text", "").strip("'\"")

"""ctags-based symbol extraction."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from src.domain.entity.symbol_def import SymbolDef


def extract_symbols(file_path: str, source: str) -> list[SymbolDef]:
    """Run universal-ctags on source to get defined symbols."""
    suffix = Path(file_path).suffix or ".txt"
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(source)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["ctags", "--output-format=json", "--fields=+neKS",
             "--kinds-all=*", "-f", "-", tmp_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    symbols: list[SymbolDef] = []
    for line in result.stdout.splitlines():
        try:
            entry = json.loads(line)
            name = entry.get("name", "")
            if name:
                symbols.append(SymbolDef(
                    name=name,
                    kind=entry.get("kind", "unknown"),
                    line=entry.get("line", 0),
                    scope=entry.get("scope", ""),
                ))
        except json.JSONDecodeError:
            continue
    return symbols

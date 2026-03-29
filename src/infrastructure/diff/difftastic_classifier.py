"""Classify diffs as structural vs cosmetic using difftastic."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from src.domain.port.diff_classifier import DiffClassifier

_STAT_RE = re.compile(r"(\d+) lines? (?:in|of) (\d+)")


class DifftasticClassifier(DiffClassifier):
    """Uses difft to distinguish structural from cosmetic changes."""

    def structural_ratio(self, file_path: str, diff_text: str) -> float:
        if not diff_text:
            return 1.0

        old_source, new_source = _reconstruct_sides(diff_text)
        if not old_source and not new_source:
            return 1.0

        return _run_difft(file_path, old_source, new_source)


def _run_difft(file_path: str, old: str, new: str) -> float:
    """Run difft --stats on two versions, return structural ratio."""
    suffix = Path(file_path).suffix or ".txt"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, prefix="old_"
    ) as f_old:
        f_old.write(old)
        old_path = f_old.name

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, prefix="new_"
    ) as f_new:
        f_new.write(new)
        new_path = f_new.name

    try:
        result = subprocess.run(
            ["difft", "--display", "json", old_path, new_path],
            capture_output=True, text=True, timeout=10,
        )
        return _parse_difft_json(result.stdout, old, new)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 1.0
    finally:
        Path(old_path).unlink(missing_ok=True)
        Path(new_path).unlink(missing_ok=True)


def _parse_difft_json(output: str, old: str, new: str) -> float:
    """Parse difft JSON output to compute structural change ratio.

    difft JSON contains hunks with 'kind' field. We count
    'novel' (structural) vs total changes.
    """
    import json
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return _parse_difft_text_fallback(old, new)

    total_hunks = 0
    novel_hunks = 0

    for file_diff in data if isinstance(data, list) else [data]:
        for hunk in file_diff.get("hunks", []):
            total_hunks += 1
            kind = hunk.get("kind", "")
            if kind != "unchanged":
                novel_hunks += 1

    if total_hunks == 0:
        return 0.0

    return round(novel_hunks / total_hunks, 2)


def _parse_difft_text_fallback(old: str, new: str) -> float:
    """Fallback: if JSON parsing fails, assume all changes are structural."""
    return 1.0


def _reconstruct_sides(diff_text: str) -> tuple[str, str]:
    """Extract old and new file content from a unified diff."""
    old_lines: list[str] = []
    new_lines: list[str] = []
    in_hunk = False

    for line in diff_text.splitlines():
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
        else:
            # Context line
            text = line[1:] if line.startswith(" ") else line
            old_lines.append(text)
            new_lines.append(text)

    return "\n".join(old_lines), "\n".join(new_lines)

"""LSP query resolver — boots LSP server, waits for index, serves queries."""

from __future__ import annotations

import sys
from pathlib import Path

from src.infrastructure.lsp.lsp_client import LspClient, detect_lsp_language, _SERVER_COMMANDS

GREEN = "\033[32m"
CYAN = "\033[36m"
DIM = "\033[2m"
YELLOW = "\033[33m"
RESET = "\033[0m"


class LspQueryResolver:
    """Boots LSP, waits for background index, serves reference queries."""

    def __init__(self, root: str):
        self._root = root
        self._client: LspClient | None = None
        self._language: str | None = None
        self._ready = False

    def start(self) -> bool:
        """Start LSP server and wait for background indexing to finish."""
        self._language = detect_lsp_language(self._root)
        if not self._language:
            return False

        self._client = LspClient(self._language, self._root)
        if not self._client.available:
            self._client = None
            return False

        info = _SERVER_COMMANDS.get(self._language, ("?", []))
        binary = info[0]
        print(f"  {CYAN}LSP: starting {binary}...{RESET}", file=sys.stderr)

        if not self._client.start():
            print(f"  {YELLOW}LSP: failed to start {binary}{RESET}", file=sys.stderr)
            self._client = None
            return False

        print(f"  {CYAN}LSP: waiting for background index...{RESET}", file=sys.stderr)
        if self._client.wait_ready():
            self._ready = True
            print(f"  {GREEN}✓{RESET} LSP: {binary} ready", file=sys.stderr)
            return True

        print(f"  {YELLOW}LSP: index timeout{RESET}", file=sys.stderr)
        self._ready = True  # use whatever is available
        return True

    def stop(self) -> None:
        if self._client:
            self._client.stop()
            self._client = None
        self._ready = False

    @property
    def available(self) -> bool:
        return self._client is not None and self._ready

    @property
    def progress_message(self) -> str:
        if self._client:
            return self._client._progress_message
        return ""

    def get_references(self, file_path: str, symbol_name: str, line: int) -> list[dict]:
        if not self._client:
            return []
        root_path = Path(self._root).resolve()
        locations = self._client.get_references(file_path, line - 1, 0)
        results = []
        for loc in locations:
            loc_uri = loc.get("uri", "") if isinstance(loc, dict) else ""
            loc_range = loc.get("range", {}) if isinstance(loc, dict) else {}
            ref_path = _uri_to_relative(loc_uri, root_path)
            if not ref_path:
                continue
            ref_line = loc_range.get("start", {}).get("line", 0) + 1
            if ref_path == file_path and ref_line == line:
                continue
            results.append({"file": ref_path, "line": ref_line})
        return results


def _uri_to_relative(uri: str, root_path: Path) -> str | None:
    if not uri.startswith("file://"):
        return None
    absolute = Path(uri.replace("file://", ""))
    try:
        return str(absolute.relative_to(root_path))
    except ValueError:
        return None

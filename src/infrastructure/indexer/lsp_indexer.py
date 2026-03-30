"""LSP-based query resolver — uses language server for on-demand precision.

LSP is NOT used during bulk indexing (too slow per-symbol).
Instead, the daemon keeps an LSP server warm and queries it
at impact time for precise references.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.infrastructure.indexer.index_store import IndexStore, SymbolEntry
from src.infrastructure.lsp.lsp_client import LspClient, detect_lsp_language

GREEN = "\033[32m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"


class LspQueryResolver:
    """On-demand LSP resolution for impact queries."""

    def __init__(self, root: str):
        self._root = root
        self._root_path = Path(root).resolve()
        self._client: LspClient | None = None
        self._language: str | None = None

    def start(self) -> bool:
        """Start the LSP server. Call once at daemon boot."""
        self._language = detect_lsp_language(self._root)
        if not self._language:
            return False

        self._client = LspClient(self._language, self._root)
        if not self._client.available:
            self._client = None
            return False

        from src.infrastructure.lsp.lsp_client import _SERVER_COMMANDS
        server_info = _SERVER_COMMANDS.get(self._language)
        binary = server_info[0] if server_info else "unknown"
        print(f"  {CYAN}LSP: detected {self._language} project, starting {binary}...{RESET}", file=sys.stderr)

        if not self._client.start():
            self._client = None
            return False

        print(f"  {GREEN}✓{RESET} LSP: {binary} started for {self._language}{RESET}", file=sys.stderr)
        self._ready = False
        return True

    def check_ready(self) -> None:
        """Check if LSP indexing is done (non-blocking). Updates _ready flag."""
        if self._ready or not self._client:
            return
        if self._client._indexing_done.is_set():
            self._ready = True

    def stop(self) -> None:
        if self._client:
            self._client.stop()
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def get_references(
        self, file_path: str, symbol_name: str, line: int,
    ) -> list[dict]:
        """Get all references to a symbol. Returns [{file, line}]."""
        if not self._client:
            return []

        try:
            locations = self._client.get_references(file_path, line - 1, 0)
        except Exception:
            return []

        results: list[dict] = []
        for location in locations:
            ref_path = _uri_to_relative(location.uri, self._root_path)
            if not ref_path:
                continue
            ref_line = location.range.start.line + 1
            if ref_path == file_path and ref_line == line:
                continue
            results.append({"file": ref_path, "line": ref_line})

        return results

    def get_incoming_calls(
        self, file_path: str, symbol_name: str, line: int,
    ) -> list[dict]:
        """Get incoming calls to a symbol. Returns [{caller_file, caller_function, line}]."""
        if not self._client:
            return []

        try:
            calls = self._client.get_call_hierarchy(file_path, line - 1, 0)
        except Exception:
            return []

        results: list[dict] = []
        for call in calls:
            caller = call.from_
            caller_path = _uri_to_relative(caller.uri, self._root_path)
            if not caller_path:
                continue
            results.append({
                "caller_file": caller_path,
                "caller_function": caller.name,
                "line": caller.range.start.line + 1,
            })

        return results


def _uri_to_relative(uri: str, root_path: Path) -> str | None:
    """Convert file:// URI to a path relative to root."""
    if not uri.startswith("file://"):
        return None
    absolute = Path(uri.replace("file://", ""))
    try:
        return str(absolute.relative_to(root_path))
    except ValueError:
        return None

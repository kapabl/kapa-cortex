"""LSP-based definition resolver — wraps LSP servers via JSON-RPC."""

from __future__ import annotations

import json
from typing import Any

from src.domain.port.definition_resolver import DefinitionLocation, DefinitionResolver
from src.infrastructure.lsp.lsp_manager import LspManager
from src.infrastructure.parsers.language_detector import detect_language


class LspDefinitionResolver(DefinitionResolver):
    """Resolve symbols via running LSP servers."""

    def __init__(self, lsp_manager: LspManager):
        self._manager = lsp_manager
        self._request_id = 0

    def resolve(
        self, file_path: str, symbol_name: str, line: int = 0,
    ) -> DefinitionLocation | None:
        lang = detect_language(file_path)
        if not lang:
            return None

        server = self._manager.get_server(lang)
        if not server or not server.running:
            return None

        response = self._send_request(server, "textDocument/definition", {
            "textDocument": {"uri": _file_uri(file_path)},
            "position": {"line": line, "character": 0},
        })

        return _parse_location(response)

    def find_references(
        self, file_path: str, symbol_name: str, line: int = 0,
    ) -> list[DefinitionLocation]:
        lang = detect_language(file_path)
        if not lang:
            return []

        server = self._manager.get_server(lang)
        if not server or not server.running:
            return []

        response = self._send_request(server, "textDocument/references", {
            "textDocument": {"uri": _file_uri(file_path)},
            "position": {"line": line, "character": 0},
            "context": {"includeDeclaration": False},
        })

        return _parse_locations(response)

    def _send_request(
        self, server, method: str, params: dict,
    ) -> dict | list | None:
        """Send a JSON-RPC request to an LSP server."""
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        payload = json.dumps(request)
        message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"

        try:
            server.process.stdin.write(message.encode("utf-8"))
            server.process.stdin.flush()
            return _read_response(server.process.stdout)
        except (BrokenPipeError, OSError, AttributeError):
            return None


def _file_uri(path: str) -> str:
    """Convert file path to file:// URI."""
    from pathlib import Path
    absolute = Path(path).resolve()
    return f"file://{absolute}"


def _read_response(stdout) -> dict | list | None:
    """Read a JSON-RPC response from LSP server stdout."""
    try:
        headers = {}
        while True:
            header_line = stdout.readline().decode("utf-8").strip()
            if not header_line:
                break
            key, value = header_line.split(": ", 1)
            headers[key] = value

        content_length = int(headers.get("Content-Length", 0))
        if content_length == 0:
            return None

        body = stdout.read(content_length).decode("utf-8")
        parsed = json.loads(body)
        return parsed.get("result")
    except (ValueError, json.JSONDecodeError, AttributeError):
        return None


def _parse_location(response: dict | list | None) -> DefinitionLocation | None:
    """Parse a single location from LSP response."""
    if not response:
        return None

    if isinstance(response, list):
        response = response[0] if response else None

    if not response:
        return None

    uri = response.get("uri", "")
    file_path = uri.replace("file://", "") if uri.startswith("file://") else uri

    position = response.get("range", {}).get("start", {})
    return DefinitionLocation(
        file_path=file_path,
        line=position.get("line", 0),
        column=position.get("character", 0),
    )


def _parse_locations(response: dict | list | None) -> list[DefinitionLocation]:
    """Parse multiple locations from LSP response."""
    if not response or not isinstance(response, list):
        return []

    results: list[DefinitionLocation] = []
    for item in response:
        location = _parse_location(item)
        if location:
            results.append(location)
    return results

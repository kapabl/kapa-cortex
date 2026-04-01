"""LSP client — JSON-RPC over stdio.

Uses asyncio subprocess directly (no pygls). Tracks $/progress
notifications for background index readiness detection.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import threading
from pathlib import Path
from typing import Any

GREEN = "\033[32m"
CYAN = "\033[36m"
DIM = "\033[2m"
YELLOW = "\033[33m"
RESET = "\033[0m"

CONTENT_LENGTH = "Content-Length: "

_SERVER_COMMANDS: dict[str, tuple[str, list[str]]] = {
    "python": ("pyright-langserver", ["pyright-langserver", "--stdio"]),
    "go": ("gopls", ["gopls", "serve"]),
    "rust": ("rust-analyzer", ["rust-analyzer"]),
    "c": ("clangd", ["clangd", "--background-index"]),
    "cpp": ("clangd", ["clangd", "--background-index"]),
    "java": ("jdtls", ["jdtls"]),
    "typescript": ("typescript-language-server", ["typescript-language-server", "--stdio"]),
    "javascript": ("typescript-language-server", ["typescript-language-server", "--stdio"]),
}


class LspClient:
    """LSP client using raw JSON-RPC over stdio."""

    def __init__(self, language: str, root_path: str):
        self._language = language
        self._root_path = Path(root_path).resolve()
        self._proc: asyncio.subprocess.Process | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._opened_files: set[str] = set()
        self._index_ready = threading.Event()
        self._active_progress: set[str] = set()
        self._progress_message = ""
        self._reader_task: asyncio.Task | None = None

    @property
    def available(self) -> bool:
        info = _SERVER_COMMANDS.get(self._language)
        if not info:
            return False
        return shutil.which(info[0]) is not None

    def start(self) -> bool:
        """Start the LSP server. Returns when initialized."""
        info = _SERVER_COMMANDS.get(self._language)
        if not info or not shutil.which(info[0]):
            return False

        started = threading.Event()

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._start_async(info[1]))
                started.set()
                self._loop.run_forever()
            except Exception as exc:
                print(f"  {YELLOW}LSP error: {exc}{RESET}", file=sys.stderr)
                started.set()

        self._loop_thread = threading.Thread(target=_run, daemon=True)
        self._loop_thread.start()
        started.wait(timeout=30)
        return self._proc is not None

    def wait_ready(self, timeout: int = 300) -> bool:
        """Block until clangd reports quiescent."""
        return self._index_ready.wait(timeout=timeout)

    def stop(self) -> None:
        if self._proc and self._loop and self._loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._loop)
                future.result(timeout=5)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)

    def get_references(self, file_path: str, line: int, column: int) -> list[dict]:
        self._ensure_open(file_path)
        uri = self._file_uri(file_path)
        result = self._request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
            "context": {"includeDeclaration": False},
        })
        return result if isinstance(result, list) else []

    def get_definition(self, file_path: str, line: int, column: int) -> dict | None:
        self._ensure_open(file_path)
        uri = self._file_uri(file_path)
        result = self._request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column},
        })
        if isinstance(result, list) and result:
            return result[0]
        return result if isinstance(result, dict) else None

    # ── Internal ──

    def _request(self, method: str, params: dict) -> Any:
        if not self._loop or not self._loop.is_running():
            return None
        future = asyncio.run_coroutine_threadsafe(
            self._send_request(method, params), self._loop,
        )
        return future.result(timeout=60)

    def _ensure_open(self, file_path: str) -> None:
        uri = self._file_uri(file_path)
        if uri in self._opened_files:
            return
        try:
            text = Path(file_path).resolve().read_text(errors="replace")
        except (FileNotFoundError, PermissionError):
            return
        lang_id = self._language if self._language != "cpp" else "cpp"
        self._notify("textDocument/didOpen", {
            "textDocument": {
                "uri": uri, "languageId": lang_id,
                "version": 1, "text": text,
            },
        })
        self._opened_files.add(uri)

    def _notify(self, method: str, params: dict) -> None:
        if not self._loop or not self._loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(
            self._send_notification(method, params), self._loop,
        )

    def _file_uri(self, path: str) -> str:
        return Path(path).resolve().as_uri()

    def _find_trigger_file(self) -> Path | None:
        """Find a source file to open, triggering CDB discovery."""
        # For C/C++: grab first file from compile_commands.json
        cdb = self._root_path / "compile_commands.json"
        if cdb.exists():
            import json as _json
            entries = _json.loads(cdb.read_text(errors="replace"))
            if entries:
                return Path(entries[0]["file"]).resolve()
        # Fallback: first matching file in root
        extensions = {
            "python": "*.py", "go": "*.go", "rust": "*.rs",
            "java": "*.java", "typescript": "*.ts", "javascript": "*.js",
        }
        pattern = extensions.get(self._language)
        if pattern:
            for match in self._root_path.glob(pattern):
                if match.is_file():
                    return match
        return None

    # ── Async protocol ──

    async def _start_async(self, command: list[str]) -> None:
        cmd = " ".join(command)
        self._proc = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.ensure_future(self._read_loop())

        # Initialize
        root_uri = self._root_path.as_uri()
        await self._send_request("initialize", {
            "rootUri": root_uri,
            "capabilities": {"window": {"workDoneProgress": True}},
            "workspaceFolders": [{"uri": root_uri, "name": "root"}],
        })
        await self._send_notification("initialized", {})

        # Open a file to trigger CDB discovery and background indexing
        trigger_file = self._find_trigger_file()
        if trigger_file:
            uri = trigger_file.as_uri()
            text = trigger_file.read_text(errors="replace")
            await self._send_notification("textDocument/didOpen", {
                "textDocument": {
                    "uri": uri, "languageId": self._language,
                    "version": 1, "text": text,
                },
            })
            self._opened_files.add(uri)

    async def _shutdown_async(self) -> None:
        try:
            await self._send_request("shutdown", None)
            await self._send_notification("exit", None)
        except Exception:
            pass
        if self._reader_task:
            self._reader_task.cancel()
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()

    async def _send_request(self, method: str, params: Any) -> Any:
        self._request_id += 1
        req_id = self._request_id
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params

        future = self._loop.create_future()
        self._pending[req_id] = future
        await self._write(msg)
        return await asyncio.wait_for(future, timeout=60)

    async def _send_notification(self, method: str, params: Any) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        await self._write(msg)

    async def _write(self, msg: dict) -> None:
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self._proc.stdin.write(header + body)
        await self._proc.stdin.drain()

    async def _read_loop(self) -> None:
        """Read JSON-RPC messages from stdout."""
        try:
            while True:
                length = await self._read_header()
                if length == 0:
                    break
                body = await self._proc.stdout.readexactly(length)
                msg = json.loads(body.decode("utf-8"))
                self._dispatch(msg)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass

    async def _read_header(self) -> int:
        headers = b""
        while b"\r\n\r\n" not in headers:
            byte = await self._proc.stdout.read(1)
            if not byte:
                return 0
            headers += byte
        for line in headers.decode("utf-8").strip().split("\r\n"):
            if line.startswith(CONTENT_LENGTH):
                return int(line[len(CONTENT_LENGTH):])
        return 0

    def _dispatch(self, msg: dict) -> None:
        """Route incoming JSON-RPC message."""
        if "id" in msg and "method" not in msg:
            # Response to our request
            req_id = msg["id"]
            if req_id in self._pending:
                future = self._pending.pop(req_id)
                if "error" in msg:
                    future.set_result(None)
                else:
                    future.set_result(msg.get("result"))
        elif "method" in msg:
            # Notification or server request
            method = msg["method"]
            params = msg.get("params", {})
            self._handle_notification(method, params, msg)

    def _handle_notification(self, method: str, params: Any, raw: dict) -> None:
        """Handle server notifications."""
        if method == "$/progress":
            token = str(params.get("token", ""))
            value = params.get("value", {})
            kind = value.get("kind", "")
            if kind == "begin":
                self._active_progress.add(token)
                title = value.get("title", "")
                self._progress_message = f"LSP: {title}"
            elif kind == "report":
                message = value.get("message", "")
                percentage = value.get("percentage")
                pct = f" {percentage}%" if percentage is not None else ""
                self._progress_message = f"LSP: {message}{pct}"
            elif kind == "end":
                self._active_progress.discard(token)
                self._progress_message = "LSP: 100%"
                if not self._active_progress:
                    self._index_ready.set()

        elif method == "window/workDoneProgress/create":
            if "id" in raw:
                asyncio.ensure_future(self._write({
                    "jsonrpc": "2.0", "id": raw["id"], "result": None,
                }))


def detect_lsp_language(root: str) -> str | None:
    root_path = Path(root)
    if (root_path / "go.mod").exists():
        return "go"
    if (root_path / "Cargo.toml").exists():
        return "rust"
    if (root_path / "CMakeLists.txt").exists() or (root_path / "compile_commands.json").exists():
        return "cpp"
    if (root_path / "pyproject.toml").exists() or (root_path / "setup.py").exists():
        return "python"
    if (root_path / "package.json").exists():
        return "typescript"
    if (root_path / "build.gradle").exists() or (root_path / "pom.xml").exists():
        return "java"
    return None

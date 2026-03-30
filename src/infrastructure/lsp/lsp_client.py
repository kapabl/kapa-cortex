"""LSP client — wraps pygls to talk to language servers."""

from __future__ import annotations

import asyncio
import shutil
import sys
import threading
from pathlib import Path

from lsprotocol import types as lsp
from pygls.lsp.client import BaseLanguageClient

GREEN = "\033[32m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"


# Language → (server binary, server command)
_SERVER_COMMANDS: dict[str, tuple[str, list[str]]] = {
    "python": ("pyright-langserver", ["pyright-langserver", "--stdio"]),
    "go": ("gopls", ["gopls", "serve"]),
    "rust": ("rust-analyzer", ["rust-analyzer"]),
    "c": ("clangd", ["clangd", "--background-index"]),
    "cpp": ("clangd", ["clangd", "--background-index"]),
    "java": ("jdtls", ["jdtls"]),
    "typescript": ("typescript-language-server", ["typescript-language-server", "--stdio"]),
    "javascript": ("typescript-language-server", ["typescript-language-server", "--stdio"]),
    "kotlin": ("kotlin-language-server", ["kotlin-language-server"]),
}


class LspClient:
    """Manages an LSP server for a single language."""

    def __init__(self, language: str, root_path: str):
        self._language = language
        self._root_path = Path(root_path).resolve()
        self._client: BaseLanguageClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._opened_files: set[str] = set()
        self._indexing_done = threading.Event()

    @property
    def available(self) -> bool:
        server_info = _SERVER_COMMANDS.get(self._language)
        if not server_info:
            return False
        binary, _ = server_info
        return shutil.which(binary) is not None

    def start(self) -> bool:
        """Start the LSP server and initialize."""
        server_info = _SERVER_COMMANDS.get(self._language)
        if not server_info:
            return False

        binary, command = server_info
        if not shutil.which(binary):
            return False

        self._loop = asyncio.new_event_loop()
        started = threading.Event()

        def _run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._start_async(command))
            started.set()
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=_run_loop, daemon=True)
        self._loop_thread.start()
        started.wait(timeout=30)
        return started.is_set()

    def wait_ready(self, timeout_seconds: int = 300) -> None:
        """Wait for the LSP server to finish indexing."""
        self._indexing_done.wait(timeout=timeout_seconds)

    def stop(self) -> None:
        """Shutdown the LSP server."""
        if self._client and self._loop:
            try:
                self._run(self._stop_async())
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._client = None
        self._loop = None

    def _run(self, coro):
        """Run an async coroutine from a sync context, thread-safe."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    def get_references(
        self, file_path: str, line: int, column: int,
    ) -> list[lsp.Location]:
        """Get all references to the symbol at the given position."""
        if not self._client or not self._loop:
            return []
        return self._run(self._references_async(file_path, line, column))

    def get_definition(
        self, file_path: str, line: int, column: int,
    ) -> lsp.Location | None:
        """Get the definition location of the symbol at the given position."""
        if not self._client or not self._loop:
            return None
        return self._run(self._definition_async(file_path, line, column))

    def get_call_hierarchy(
        self, file_path: str, line: int, column: int,
    ) -> list[lsp.CallHierarchyIncomingCall]:
        """Get incoming calls to the symbol at the given position."""
        if not self._client or not self._loop:
            return []
        return self._run(self._incoming_calls_async(file_path, line, column))

    async def _start_async(self, command: list[str]) -> None:
        self._client = BaseLanguageClient("kapa-cortex", "0.1.0")
        self._active_progress: set[str] = set()

        @self._client.feature("textDocument/publishDiagnostics")
        def _on_diagnostics(params):
            pass

        @self._client.feature("$/progress")
        def _on_progress(params):
            token = str(params.token)
            value = params.value
            kind = getattr(value, "kind", None)
            if kind == "begin":
                self._active_progress.add(token)
                title = getattr(value, "title", "")
                if title:
                    print(f"\r\033[2K  {CYAN}LSP: {title}{RESET}", end="", file=sys.stderr, flush=True)
            elif kind == "report":
                message = getattr(value, "message", "")
                percentage = getattr(value, "percentage", None)
                if message or percentage is not None:
                    pct = f" {percentage}%" if percentage is not None else ""
                    print(f"\r\033[2K  {CYAN}LSP: {message}{pct}{RESET}", end="", file=sys.stderr, flush=True)
            elif kind == "end":
                self._active_progress.discard(token)
                message = getattr(value, "message", "done")
                print(f"\r\033[2K  {GREEN}✓{RESET} LSP: {message}", file=sys.stderr)
                if not self._active_progress:
                    self._indexing_done.set()

        @self._client.feature("window/workDoneProgress/create")
        def _on_create_progress(params):
            return None

        await self._client.start_io(*command)
        root_uri = self._root_path.as_uri()
        await self._client.initialize_async(lsp.InitializeParams(
            root_uri=root_uri,
            capabilities=lsp.ClientCapabilities(
                window=lsp.WindowClientCapabilities(
                    work_done_progress=True,
                ),
            ),
            workspace_folders=[
                lsp.WorkspaceFolder(uri=root_uri, name="root"),
            ],
        ))
        self._client.initialized(lsp.InitializedParams())

    async def _stop_async(self) -> None:
        await self._client.shutdown_async(None)
        self._client.exit(None)

    async def _ensure_open(self, file_path: str) -> str:
        """Ensure a file is opened in the LSP server."""
        absolute = str(Path(file_path).resolve())
        uri = Path(absolute).as_uri()
        if uri not in self._opened_files:
            source = Path(absolute).read_text(errors="replace")
            language_id = _language_id(self._language)
            self._client.text_document_did_open(lsp.DidOpenTextDocumentParams(
                text_document=lsp.TextDocumentItem(
                    uri=uri,
                    language_id=language_id,
                    version=1,
                    text=source,
                ),
            ))
            self._opened_files.add(uri)
        return uri

    async def _references_async(
        self, file_path: str, line: int, column: int,
    ) -> list[lsp.Location]:
        uri = await self._ensure_open(file_path)
        result = await self._client.text_document_references_async(
            lsp.ReferenceParams(
                text_document=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=column),
                context=lsp.ReferenceContext(include_declaration=False),
            ),
        )
        return result or []

    async def _definition_async(
        self, file_path: str, line: int, column: int,
    ) -> lsp.Location | None:
        uri = await self._ensure_open(file_path)
        result = await self._client.text_document_definition_async(
            lsp.DefinitionParams(
                text_document=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=column),
            ),
        )
        if isinstance(result, list) and result:
            return result[0]
        return result if isinstance(result, lsp.Location) else None

    async def _incoming_calls_async(
        self, file_path: str, line: int, column: int,
    ) -> list[lsp.CallHierarchyIncomingCall]:
        uri = await self._ensure_open(file_path)
        items = await self._client.text_document_prepare_call_hierarchy_async(
            lsp.CallHierarchyPrepareParams(
                text_document=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=column),
            ),
        )
        if not items:
            return []
        calls = await self._client.call_hierarchy_incoming_calls_async(
            lsp.CallHierarchyIncomingCallsParams(item=items[0]),
        )
        return calls or []


def detect_lsp_language(root: str) -> str | None:
    """Detect the primary language of a repo from project files."""
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


def _language_id(language: str) -> str:
    """Map internal language name to LSP languageId."""
    mapping = {
        "python": "python",
        "go": "go",
        "rust": "rust",
        "c": "c",
        "cpp": "cpp",
        "java": "java",
        "kotlin": "kotlin",
        "typescript": "typescript",
        "javascript": "javascript",
    }
    return mapping.get(language, language)

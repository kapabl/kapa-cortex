"""Manage LSP server lifecycles — boot, health check, restart."""

from __future__ import annotations

import subprocess
import shutil
import threading
import time
from dataclasses import dataclass, field


@dataclass
class LspServerConfig:
    """Configuration for a single LSP server."""

    name: str
    command: list[str]
    languages: list[str]
    binary: str  # binary to check in PATH


@dataclass
class LspServerState:
    """Runtime state of a managed LSP server."""

    config: LspServerConfig
    process: subprocess.Popen | None = None
    healthy: bool = False
    start_time: float = 0.0

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None


# Default server configurations
DEFAULT_SERVERS = [
    LspServerConfig(
        name="pyright",
        command=["pyright-langserver", "--stdio"],
        languages=["python"],
        binary="pyright-langserver",
    ),
    LspServerConfig(
        name="clangd",
        command=["clangd", "--background-index"],
        languages=["c", "cpp"],
        binary="clangd",
    ),
    LspServerConfig(
        name="gopls",
        command=["gopls", "serve"],
        languages=["go"],
        binary="gopls",
    ),
    LspServerConfig(
        name="jdtls",
        command=["jdtls"],
        languages=["java"],
        binary="jdtls",
    ),
    LspServerConfig(
        name="rust-analyzer",
        command=["rust-analyzer"],
        languages=["rust"],
        binary="rust-analyzer",
    ),
]


class LspManager:
    """Boot and manage LSP servers for the daemon."""

    def __init__(self, configs: list[LspServerConfig] | None = None):
        self._configs = configs or DEFAULT_SERVERS
        self._servers: dict[str, LspServerState] = {}
        self._health_thread: threading.Thread | None = None
        self._running = False

    def boot(self) -> dict[str, bool]:
        """Boot all available LSP servers in parallel. Returns name → success."""
        threads: list[threading.Thread] = []
        results: dict[str, bool] = {}

        for config in self._configs:
            if not shutil.which(config.binary):
                results[config.name] = False
                continue

            thread = threading.Thread(
                target=self._boot_server,
                args=(config, results),
                daemon=True,
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=30)

        self._running = True
        self._start_health_check()
        return results

    def shutdown(self) -> None:
        """Stop all LSP servers."""
        self._running = False
        if self._health_thread:
            self._health_thread.join(timeout=5)

        for state in self._servers.values():
            if state.running:
                state.process.terminate()
                try:
                    state.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    state.process.kill()

        self._servers.clear()

    def status(self) -> dict[str, dict]:
        """Return status of all managed servers."""
        result: dict[str, dict] = {}
        for name, state in self._servers.items():
            result[name] = {
                "running": state.running,
                "healthy": state.healthy,
                "languages": state.config.languages,
                "uptime": round(time.time() - state.start_time, 1) if state.running else 0,
            }

        for config in self._configs:
            if config.name not in result:
                result[config.name] = {
                    "running": False,
                    "healthy": False,
                    "languages": config.languages,
                    "installed": bool(shutil.which(config.binary)),
                }

        return result

    def get_server(self, language: str) -> LspServerState | None:
        """Get the running server for a language."""
        for state in self._servers.values():
            if language in state.config.languages and state.running:
                return state
        return None

    def _boot_server(
        self, config: LspServerConfig, results: dict[str, bool],
    ) -> None:
        """Boot a single LSP server."""
        try:
            process = subprocess.Popen(
                config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            state = LspServerState(
                config=config,
                process=process,
                healthy=True,
                start_time=time.time(),
            )
            self._servers[config.name] = state
            results[config.name] = True
        except (FileNotFoundError, OSError):
            results[config.name] = False

    def _start_health_check(self) -> None:
        """Start background health check loop."""
        self._health_thread = threading.Thread(
            target=self._health_loop, daemon=True,
        )
        self._health_thread.start()

    def _health_loop(self) -> None:
        """Check server health every 10 seconds, restart crashed ones."""
        while self._running:
            time.sleep(10)
            for name, state in list(self._servers.items()):
                if not state.running and state.healthy:
                    state.healthy = False
                    self._restart_server(state)

    def _restart_server(self, state: LspServerState) -> None:
        """Attempt to restart a crashed server."""
        try:
            process = subprocess.Popen(
                state.config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            state.process = process
            state.healthy = True
            state.start_time = time.time()
        except (FileNotFoundError, OSError):
            state.healthy = False

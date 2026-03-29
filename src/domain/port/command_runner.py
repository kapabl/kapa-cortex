"""Port: shell command execution."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CommandRunner(ABC):
    """Contract for running shell commands. Implemented by infrastructure."""

    @abstractmethod
    def run(self, cmd: str, dry_run: bool = False) -> tuple[bool, str]: ...

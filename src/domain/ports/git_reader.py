"""Port: git operations the domain needs."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.changed_file import ChangedFile


class GitReader(ABC):
    """Contract for reading git state. Implemented by infrastructure."""

    @abstractmethod
    def current_branch(self) -> str: ...

    @abstractmethod
    def resolve_base(self, base: str) -> str: ...

    @abstractmethod
    def merge_base(self, base_ref: str) -> str: ...

    @abstractmethod
    def diff_stat(self, base_ref: str) -> list[ChangedFile]: ...

    @abstractmethod
    def file_source(self, path: str) -> str: ...

    @abstractmethod
    def cochange_history(
        self, paths: list[str], max_commits: int = 200,
    ) -> dict[tuple[str, str], int]: ...

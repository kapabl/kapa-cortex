"""Port: co-change history between files."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CochangeProvider(ABC):
    """Contract for retrieving file co-change data."""

    @abstractmethod
    def cochange_history(
        self, paths: list[str],
    ) -> dict[tuple[str, str], int]: ...

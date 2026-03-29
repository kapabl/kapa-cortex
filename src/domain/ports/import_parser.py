"""Port: import/dependency extraction from source code."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.import_ref import ImportRef


class ImportParser(ABC):
    """Contract for parsing imports. Implemented by infrastructure."""

    @abstractmethod
    def parse(self, file_path: str, source: str) -> list[ImportRef]: ...

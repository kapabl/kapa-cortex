"""Port: symbol definition extraction from source code."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.symbol_def import SymbolDef


class SymbolExtractor(ABC):
    """Contract for extracting symbols. Implemented by infrastructure."""

    @abstractmethod
    def extract(self, file_path: str, source: str) -> list[SymbolDef]: ...

"""Port: local LLM for smart analysis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from any LLM backend."""

    text: str
    model: str
    backend: str
    tokens_used: int = 0
    duration_ms: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text) and not self.error


class LLMService(ABC):
    """Contract for LLM backends. Implemented by infrastructure."""

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def query(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse: ...

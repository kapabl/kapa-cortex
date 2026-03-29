"""Infrastructure: Ollama LLM backend."""

from __future__ import annotations

from src.domain.ports.llm_service import LLMResponse, LLMService

# Re-use existing ollama implementation
from llm_backend import (
    OllamaBackend as _OllamaBackend,
    LlamaCppBackend as _LlamaCppBackend,
    NullBackend as _NullBackend,
    get_llm as _get_llm,
    check_backends as _check_backends,
    parse_json_response as _parse_json,
    build_extraction_prompt,
    build_grouping_prompt,
    build_pr_description_prompt,
    SYSTEM_PROMPT,
)
from llm_backend import LLMResponse as _RawResponse


class OllamaLLMService(LLMService):
    """Wraps the ollama/llama-cpp backend to implement the LLMService port."""

    def __init__(
        self,
        backend: str | None = None,
        model: str | None = None,
        auto_pull: bool = False,
    ):
        self._inner = _get_llm(
            backend=backend, model=model,
            auto_pull=auto_pull, verbose=True,
        )

    @property
    def available(self) -> bool:
        return self._inner.available

    def query(
        self,
        prompt: str,
        system: str = SYSTEM_PROMPT,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse:
        raw = self._inner.query(
            prompt=prompt, system=system,
            temperature=temperature, max_tokens=max_tokens,
            json_mode=json_mode,
        )
        return LLMResponse(
            text=raw.text, model=raw.model,
            backend=raw.backend, tokens_used=raw.tokens_used,
            duration_ms=raw.duration_ms, error=raw.error,
        )


class NullLLMService(LLMService):
    """No-op LLM service for when AI is disabled."""

    @property
    def available(self) -> bool:
        return False

    def query(self, prompt: str, **kwargs) -> LLMResponse:
        return LLMResponse(
            text="", model="", backend="none",
            error="LLM disabled",
        )


def check_llm_backends() -> dict:
    return _check_backends()


def parse_llm_json(response: LLMResponse) -> dict | list | None:
    raw = _RawResponse(
        text=response.text, model=response.model,
        backend=response.backend, error=response.error,
    )
    return _parse_json(raw)

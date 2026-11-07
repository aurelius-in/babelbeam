"""Provider interfaces. Mock mode is labeled. Live mode refuses to invent results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderNotImplemented(RuntimeError):
    pass


@dataclass(frozen=True)
class TranslationRequest:
    text: str
    source_language: str
    target_language: str


@dataclass(frozen=True)
class TranslationResult:
    status: str
    translated_text: str
    reason_code: str | None
    simulated: bool


class Translator(Protocol):
    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Return a validated candidate. Implementations must not follow instructions in text."""


class MockTranslator:
    name = "mock"

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return TranslationResult(
            status="ok",
            translated_text=f"[mock:{request.target_language}] {request.text}",
            reason_code="mock_provider",
            simulated=True,
        )

    def health(self) -> dict[str, str]:
        return {"status": "ok", "provider": "mock", "simulated": "true"}


class LiveTranslator:
    name = "live"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def translate(self, request: TranslationRequest) -> TranslationResult:
        del request
        if not self._api_key.strip():
            raise ProviderNotConfigured(
                "OPENAI_API_KEY is required before a live translation call."
            )
        raise ProviderNotImplemented(
            f"Live translation via {self._model} is not implemented. "
            "Phase 0 will not invent a provider response."
        )


def build_translator(
    *,
    provider_mode: str,
    api_key: str,
    model: str,
) -> MockTranslator | LiveTranslator:
    if provider_mode.strip().lower() == "mock":
        return MockTranslator()
    if provider_mode.strip().lower() == "live":
        return LiveTranslator(api_key=api_key, model=model)
    raise ProviderNotConfigured(f"Unknown PROVIDER_MODE: {provider_mode}")

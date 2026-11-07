from __future__ import annotations

import socket

import pytest

from babelbeam_runtime import Settings, validate_settings
from babelbeam_runtime.config import PLAN_PATH
from worker.providers import (
    LiveTranslator,
    MockTranslator,
    ProviderNotConfigured,
    ProviderNotImplemented,
    TranslationRequest,
    build_translator,
)


def test_mock_translation_is_labeled_and_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("mock translator tried to open a socket")

    monkeypatch.setattr(socket, "socket", explode)
    result = MockTranslator().translate(
        TranslationRequest(text="Peace be with you.", source_language="en", target_language="es")
    )
    assert result.simulated is True
    assert result.translated_text.startswith("[mock:es]")
    assert result.reason_code == "mock_provider"


def test_live_translator_refuses_missing_key_and_does_not_invent_text() -> None:
    translator = LiveTranslator(api_key="", model="gpt-5.4-mini-2026-03-17")
    with pytest.raises(ProviderNotConfigured):
        translator.translate(
            TranslationRequest(text="Hello", source_language="en", target_language="es")
        )


def test_live_translator_with_a_key_still_does_not_call_out() -> None:
    translator = LiveTranslator(api_key="sk-test-not-used", model="gpt-5.4-mini-2026-03-17")
    with pytest.raises(ProviderNotImplemented):
        translator.translate(
            TranslationRequest(text="Hello", source_language="en", target_language="es")
        )


def test_factory_selects_mock_only_when_asked() -> None:
    assert isinstance(build_translator(provider_mode="mock", api_key="", model="m"), MockTranslator)
    live = build_translator(provider_mode="live", api_key="", model="m")
    assert isinstance(live, LiveTranslator)


def test_worker_settings_reject_production_mock() -> None:
    with pytest.raises(RuntimeError, match="PROVIDER_MODE=mock"):
        validate_settings(
            Settings(
                environment="production",
                provider_mode="mock",
                plan_path=PLAN_PATH,
                _env_file=None,
            )
        )

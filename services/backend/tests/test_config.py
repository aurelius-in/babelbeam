from __future__ import annotations

from pathlib import Path

import pytest

from babelbeam_runtime import Settings, validate_settings
from babelbeam_runtime.config import PLAN_PATH


def _settings(**overrides: object) -> Settings:
    raw: dict[str, object] = {"plan_path": PLAN_PATH, "_env_file": None}
    raw.update(overrides)
    return Settings(**raw)  # type: ignore[arg-type]


def test_development_mock_mode_is_allowed() -> None:
    validate_settings(_settings())


def test_production_rejects_mock_providers() -> None:
    with pytest.raises(RuntimeError, match="PROVIDER_MODE=mock"):
        validate_settings(
            _settings(
                environment="production",
                provider_mode="mock",
                app_origin="https://babelbeam.example",
            )
        )


def test_production_rejects_example_secrets_and_local_database() -> None:
    with pytest.raises(RuntimeError, match="APP_SESSION_HASH_KEY"):
        validate_settings(
            _settings(
                environment="production",
                provider_mode="live",
                app_origin="https://babelbeam.example",
                app_session_hash_key="change-me-in-local-env-not-long-enough",
                csrf_signing_key="x" * 40,
                trial_eligibility_hmac_key="y" * 40,
                internal_worker_auth_key="z" * 40,
                database_url="postgresql+psycopg://postgres:postgres@localhost:5432/babelbeam",
                redis_url="rediss://cache.internal:6379/0",
            )
        )


def test_recording_and_billing_flags_are_refused(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="RECORD_CLASSROOM_AUDIO"):
        validate_settings(_settings(record_classroom_audio=True))
    with pytest.raises(RuntimeError, match="PRODUCTION_BILLING_ENABLED"):
        validate_settings(_settings(production_billing_enabled=True))
    with pytest.raises(RuntimeError, match="MINORS_ENABLED"):
        validate_settings(_settings(minors_enabled=True))
    assert tmp_path is not None


def test_live_mode_refuses_to_start_without_a_speech_key() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        validate_settings(_settings(provider_mode="live", openai_api_key=""))


def test_price_must_stay_1499_cents() -> None:
    with pytest.raises(RuntimeError, match="1499"):
        validate_settings(_settings(plan_amount_cents=1000))

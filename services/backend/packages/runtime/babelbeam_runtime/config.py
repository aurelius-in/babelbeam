"""Environment contract. Production refuses simulated providers and example secrets."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PUBLIC_SITE_ORIGINS = (
    "https://babelbeam.com",
    "https://www.babelbeam.com",
    "https://babelbeam.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def discover_plan_path() -> Path:
    """Find config/plan.json from the repo, then the copy shipped inside this package."""
    override = os.environ.get("BABELBEAM_PLAN_PATH", "").strip()
    if override:
        return Path(override)
    starts = [Path.cwd(), Path(__file__).resolve()]
    seen: set[Path] = set()
    for start in starts:
        for parent in (start, *start.parents):
            if parent in seen:
                continue
            seen.add(parent)
            candidate = parent / "config" / "plan.json"
            if candidate.is_file():
                return candidate
    return Path(__file__).resolve().parent / "plan.json"


PLAN_PATH = discover_plan_path()

INSECURE_SECRET_MARKERS = (
    "change-me",
    "changeme",
    "replace-me",
    "example",
    "password",
    "secret",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    provider_mode: str = "mock"
    production_billing_enabled: bool = False
    plan_limits_approved: bool = False
    minors_enabled: bool = False
    app_origin: str = "http://localhost:5173"
    api_public_prefix: str = "/api/v1"
    ws_public_prefix: str = "/ws/v1"
    app_session_hash_key: str = ""
    csrf_signing_key: str = ""
    trial_eligibility_hmac_key: str = ""
    internal_worker_auth_key: str = ""
    database_url: str = ""
    redis_url: str = ""
    auth_provider: str = "supabase"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    support_email: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_monthly_price_id: str = ""
    stripe_api_version: str = ""
    stripe_automatic_tax_enabled: bool = False
    stripe_trial_days: int = 14
    plan_amount_cents: int = 1499
    plan_currency: str = "usd"
    plan_interval: str = "month"
    plan_included_class_seconds: int = 18000
    plan_trial_class_seconds: int = 18000
    plan_max_student_listeners: int = 10
    plan_max_concurrent_classes: int = 1
    plan_max_teacher_seats: int = 1
    class_max_seconds: int = 5400
    class_wind_down_seconds: int = 600
    class_idle_timeout_seconds: int = 300
    class_paused_timeout_seconds: int = 900
    floor_grant_timeout_seconds: int = 20
    floor_max_speaking_seconds: int = 90
    past_due_existing_paid_grace_seconds: int = 259200
    max_global_active_classes: int = 3
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    openai_api_key: str = ""
    openai_stt_model: str = "gpt-live-transcribe"
    openai_translation_model: str = "gpt-5.4-mini-2026-03-17"
    openai_translation_reasoning_effort: str = "none"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice_es: str = "marin"
    openai_tts_voice_en: str = "marin"
    stt_pcm_sample_rate: int = 24000
    audio_frame_ms: int = 20
    audio_backlog_warning_seconds: int = 8
    audio_backlog_max_seconds: int = 20
    class_caption_ttl_seconds: int = 300
    class_caption_max_segments: int = 100
    record_classroom_audio: bool = False
    persist_classroom_transcripts: bool = False
    monthly_provider_budget_usd: str = ""
    trial_acquisition_budget_usd: str = ""
    plan_path: Path = Field(default=PLAN_PATH)


def load_plan(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"Plan file is missing: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Plan file must be a JSON object: {path}")
    return loaded


def _secret_is_unsafe(value: str) -> bool:
    lowered = value.strip().lower()
    if len(lowered) < 32:
        return True
    return any(marker in lowered for marker in INSECURE_SECRET_MARKERS)


def validate_settings(settings: Settings) -> None:
    """Fail closed. Development may run in mock mode. Production may not."""
    problems: list[str] = []
    environment = settings.environment.strip().lower()
    provider_mode = settings.provider_mode.strip().lower()

    if environment not in {"development", "test", "production"}:
        problems.append("ENVIRONMENT must be development, test, or production.")
    if provider_mode not in {"mock", "live"}:
        problems.append("PROVIDER_MODE must be mock or live.")
    if settings.record_classroom_audio or settings.persist_classroom_transcripts:
        problems.append(
            "RECORD_CLASSROOM_AUDIO and PERSIST_CLASSROOM_TRANSCRIPTS must stay false."
        )
    if settings.minors_enabled:
        problems.append(
            "MINORS_ENABLED must stay false until an approved consent workflow exists."
        )
    if settings.production_billing_enabled:
        problems.append(
            "PRODUCTION_BILLING_ENABLED must stay false until billing is implemented and approved."
        )
    if settings.plan_amount_cents != 1499 or settings.plan_currency.lower() != "usd":
        problems.append("The confirmed price is 1499 USD cents.")
    if settings.stripe_trial_days != 14:
        problems.append("The confirmed trial length is 14 days.")
    if provider_mode == "live" and not settings.openai_api_key.strip():
        problems.append("PROVIDER_MODE=live requires OPENAI_API_KEY. Refusing to start without it.")

    try:
        plan = load_plan(settings.plan_path)
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        problems.append(str(exc))
        plan = {}

    if plan:
        if plan.get("amount_cents") != settings.plan_amount_cents:
            problems.append("PLAN_AMOUNT_CENTS does not match config/plan.json.")
        if plan.get("currency") != settings.plan_currency:
            problems.append("PLAN_CURRENCY does not match config/plan.json.")
        if plan.get("trial_days") != settings.stripe_trial_days:
            problems.append("STRIPE_TRIAL_DAYS does not match config/plan.json.")
        if plan.get("student_price_cents") != 0:
            problems.append("Students are not billed. student_price_cents must be 0.")

    if environment == "production":
        if provider_mode != "live":
            problems.append("Production refuses PROVIDER_MODE=mock.")
        if not settings.app_origin.startswith("https://"):
            problems.append("Production APP_ORIGIN must be https.")
        for name, value in (
            ("APP_SESSION_HASH_KEY", settings.app_session_hash_key),
            ("CSRF_SIGNING_KEY", settings.csrf_signing_key),
            ("TRIAL_ELIGIBILITY_HMAC_KEY", settings.trial_eligibility_hmac_key),
            ("INTERNAL_WORKER_AUTH_KEY", settings.internal_worker_auth_key),
        ):
            if _secret_is_unsafe(value):
                problems.append(f"{name} must be a unique secret of at least 32 characters.")
        database = settings.database_url.lower()
        if not database.startswith("postgresql"):
            problems.append("Production DATABASE_URL must be a PostgreSQL URL.")
        if "postgres:postgres@" in database or "localhost" in database or "127.0.0.1" in database:
            problems.append("Production DATABASE_URL must not use local example credentials.")
        if not settings.redis_url.startswith("rediss://"):
            problems.append("Production REDIS_URL must use rediss:// on a private host.")
        if "*" in settings.app_origin:
            problems.append("Wildcard origins are not allowed.")

    if problems:
        joined = "\n".join(f"- {problem}" for problem in problems)
        raise RuntimeError(f"Refusing to start BabelBeam:\n{joined}")


def allowed_origins(settings: Settings) -> list[str]:
    origins = list(PUBLIC_SITE_ORIGINS)
    origin = settings.app_origin.strip()
    if origin and origin not in origins and "*" not in origin:
        origins.append(origin)
    return origins


def simulated(settings: Settings) -> bool:
    return settings.provider_mode.strip().lower() != "live"

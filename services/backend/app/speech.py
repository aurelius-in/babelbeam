"""Bounded speech-to-text. No audio or transcript logging."""

from __future__ import annotations

import httpx

from app import timing
from babelbeam_runtime import Settings

# File turns use the documented transcription model. gpt-live-transcribe is a
# realtime session and this host does not keep that socket open.
FILE_STT_MODEL = "gpt-transcribe"
_MAX_AUDIO_BYTES = 2_000_000
_MEDIA_TYPES = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
}


def transcribe_audio(
    settings: Settings,
    audio: bytes,
    content_type: str,
    languages_out: list[str] | None = None,
    prompt: str = "",
) -> str:
    """Transcribe one finished utterance. Detected language codes go to languages_out."""
    if settings.provider_mode.strip().lower() != "live":
        raise RuntimeError("Speech transcription is not available without a live speech provider.")
    if not settings.openai_api_key.strip():
        raise RuntimeError("OPENAI_API_KEY is required before a live transcription call.")
    media_type, extension = _media_type(content_type)
    if not audio or len(audio) < 400:
        raise ValueError("Audio is empty.")
    if len(audio) > _MAX_AUDIO_BYTES:
        raise ValueError("Audio is too large.")
    try:
        with timing.stage("stt"):
            response = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                files={"file": (f"speech.{extension}", audio, media_type)},
                data=_transcription_data(prompt),
                timeout=40.0,
            )
    except httpx.HTTPError as exc:
        raise RuntimeError("The transcription provider could not be reached.") from exc
    if response.status_code != 200:
        raise RuntimeError("The transcription provider rejected the request.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("The transcription provider returned no text.") from exc
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str):
        raise RuntimeError("No speech was recognized.")
    if languages_out is not None and isinstance(payload, dict):
        detected = payload.get("languages")
        if isinstance(detected, list):
            for item in detected:
                code = item.get("code") if isinstance(item, dict) else None
                if isinstance(code, str) and code.strip():
                    languages_out.append(code.strip().lower()[:12])
    cleaned = " ".join(text.split())
    if not cleaned or not any(character.isalnum() for character in cleaned):
        raise RuntimeError("No speech was recognized.")
    return cleaned[:400]


def _transcription_data(prompt: str) -> dict[str, str]:
    data = {"model": FILE_STT_MODEL}
    cleaned = " ".join(prompt.split())
    if cleaned:
        data["prompt"] = cleaned[:500]
    return data


def _media_type(content_type: str) -> tuple[str, str]:
    media_type = content_type.split(";", 1)[0].strip().lower()
    extension = _MEDIA_TYPES.get(media_type)
    if extension is None:
        raise ValueError("Audio type is not supported.")
    return media_type, extension

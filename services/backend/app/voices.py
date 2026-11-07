"""Student-selectable Spanish class voices.

Owner decision 2026-10-24: each student picks one of four AI-generated voices. They are
synthetic voices, not recordings or likenesses of real people. A class line is synthesized
once per voice that at least one joined student selected, never once per listener.

The provider voice names are documented OpenAI built-in voices that also appear in the
Realtime voice list. The steering text goes to the documented `instructions` parameter of
gpt-4o-mini-tts. It is fixed server text, never class content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

VoiceId = Literal["felipe", "roberta", "mateo", "valeria"]

VOICE_IDS: Final[tuple[VoiceId, ...]] = ("felipe", "roberta", "mateo", "valeria")
DEFAULT_VOICE: Final[VoiceId] = "valeria"

_ACCENT = (
    "Accent: natural, neutral Latin American Spanish, as spoken by Mexican families "
    "in the United States."
)
_EXACT = "Read the text exactly as written, without adding, skipping, or repeating words."


@dataclass(frozen=True)
class ClassVoice:
    voice_id: VoiceId
    provider_voice: str
    instructions: str


def _steer(voice: str, tone: str, pacing: str) -> str:
    return "\n".join(
        (f"Voice: {voice}", _ACCENT, f"Tone: {tone}", f"Pacing: {pacing}", _EXACT)
    )


_OLDER_PACE = "unhurried and clear, with short natural pauses at commas and periods."
_YOUNGER_PACE = "a natural conversational pace, clear and steady."

CLASS_VOICES: Final[dict[VoiceId, ClassVoice]] = {
    "felipe": ClassVoice(
        "felipe",
        "cedar",
        _steer(
            "a warm older man in his seventies, a kind grandfather who has served his "
            "parish for many years. The natural texture of age, a little lower and softer, "
            "never shaky or theatrical.",
            "gentle, reverent, and reassuring, for a parish class.",
            _OLDER_PACE,
        ),
    ),
    "roberta": ClassVoice(
        "roberta",
        "sage",
        _steer(
            "a warm older woman in her seventies, a kind grandmother who has taught "
            "catechism for many years. The natural texture of age, a little lower and "
            "softer, never shaky or theatrical.",
            "patient, tender, and reassuring, for a parish class.",
            _OLDER_PACE,
        ),
    ),
    "mateo": ClassVoice(
        "mateo",
        "verse",
        _steer(
            "a friendly young man in his twenties, a youth minister at the parish. "
            "Bright, relaxed, and natural.",
            "warm, sincere, and respectful, for a parish class.",
            _YOUNGER_PACE,
        ),
    ),
    "valeria": ClassVoice(
        "valeria",
        "marin",
        _steer(
            "a friendly young woman in her twenties, a parish volunteer. "
            "Bright, warm, and natural.",
            "kind, sincere, and respectful, for a parish class.",
            _YOUNGER_PACE,
        ),
    ),
}


def parse_voice(value: object) -> VoiceId | None:
    """Return one of the four voice IDs, or None for anything else."""
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    for voice_id in VOICE_IDS:
        if key == voice_id:
            return voice_id
    return None


def class_voice(voice_id: VoiceId) -> ClassVoice:
    return CLASS_VOICES[voice_id]

"""Student speaker gender for teacher-side English question playback.

Owner decision 2026-10-24: students are young adults. Boy/girl on join maps to the same
provider voices as Mateo and Valeria (verse / marin), with English young-man / young-woman
steering for the question the teacher hears. Not child voices. Synthetic only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.voices import class_voice

SpeakerGender = Literal["boy", "girl"]

GENDER_IDS: Final[tuple[SpeakerGender, ...]] = ("boy", "girl")
DEFAULT_GENDER: Final[SpeakerGender] = "girl"

_EXACT = "Read the text exactly as written, without adding, skipping, or repeating words."
_ENGLISH = "Accent: clear American English."


@dataclass(frozen=True)
class GenderReplyVoice:
    gender: SpeakerGender
    provider_voice: str
    instructions: str


def _english_steer(voice: str, tone: str, pacing: str) -> str:
    return "\n".join(
        (f"Voice: {voice}", _ENGLISH, f"Tone: {tone}", f"Pacing: {pacing}", _EXACT)
    )


# Provider voices match Mateo (verse) and Valeria (marin). Instructions are English
# young-adult question playback for the teacher, not Spanish class listen personas.
GENDER_REPLY_VOICES: Final[dict[SpeakerGender, GenderReplyVoice]] = {
    "boy": GenderReplyVoice(
        "boy",
        class_voice("mateo").provider_voice,
        _english_steer(
            "a friendly young man in his twenties asking a question in class. "
            "Bright, relaxed, and natural.",
            "warm, sincere, and respectful, as a student speaking to the catechist.",
            "a natural conversational pace, clear and steady.",
        ),
    ),
    "girl": GenderReplyVoice(
        "girl",
        class_voice("valeria").provider_voice,
        _english_steer(
            "a friendly young woman in her twenties asking a question in class. "
            "Bright, warm, and natural.",
            "kind, sincere, and respectful, as a student speaking to the catechist.",
            "a natural conversational pace, clear and steady.",
        ),
    ),
}


def parse_gender(value: object) -> SpeakerGender | None:
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    if key in {"boy", "male", "m", "hombre", "nino", "niño"}:
        return "boy"
    if key in {"girl", "female", "f", "mujer", "nina", "niña"}:
        return "girl"
    return None


def gender_reply_voice(gender: SpeakerGender) -> GenderReplyVoice:
    return GENDER_REPLY_VOICES[gender]

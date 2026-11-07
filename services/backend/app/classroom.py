"""Live class board. Session state only. Nothing here is written to logs."""

from __future__ import annotations

import concurrent.futures
import json
import os
import secrets
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app import board_merge, timing
from app.interpret import interpret_text, synthesize_line, synthesize_speech
from app.phrase_cleanup import (
    ContextLine,
    ContextLineIn,
    Interpretation,
    bound_context,
    interpret_phrase,
    is_filler_only,
    parse_mode,
    transcription_prompt,
)
from app.say_next import suggest_next
from app.speech import transcribe_audio
from app.speaker_gender import (
    DEFAULT_GENDER,
    SpeakerGender,
    gender_reply_voice,
    parse_gender,
)
from app.student_name import sanitize_display_name
from app.voices import DEFAULT_VOICE, VOICE_IDS, VoiceId, class_voice, parse_voice
from app import lessons
from app.errors import ClassError
from babelbeam_runtime import Settings

_LOCK = threading.Lock()
_BOARD: dict[str, Any] = {"rooms": [], "revision": 0}
_LOADED = False
_LOADED_AT = 0.0
_BLOB_PREFIX = "classroom/boards/"
_KEEP_AFTER_END_SECONDS = 120
_KEEP_LIVE_SECONDS = 8 * 60 * 60
_MAX_SEGMENTS = 30
# Older lines keep their caption but drop audio so every snapshot stays small.
_SEGMENTS_WITH_AUDIO = 8
# Cap stored clips so four voices cannot grow the board without bound.
_MAX_CLIPS = 8
# Snapshots merged per read. Writers prune what they merged, so a handful remain.
_READ_LIMIT = 12
# Student feed polls on one warm instance share a board read this fresh.
_FEED_CACHE_SECONDS = 0.75
_PRUNE_WAIT_SECONDS = 2.0
_MAX_SEQ = 1_000_000
_MAX_WAIT_FOR = 8
# Pathnames merged into the in-memory board by the latest read or write.
_MERGED_PATHNAMES: list[str] = []
_IO_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="bb-board")


def reset_classes() -> None:
    global _LOADED
    with _LOCK:
        _BOARD["rooms"] = []
        _BOARD["revision"] = 0
        _MERGED_PATHNAMES.clear()
        _LOADED = True
        _persist_unlocked()


def start_class() -> dict[str, str]:
    with _LOCK:
        _load_unlocked()
        _purge_unlocked()
        code = _new_code_unlocked()
        teacher_token = secrets.token_urlsafe(24)
        room: dict[str, Any] = {
            "id": secrets.token_urlsafe(12),
            "code": code,
            "teacher_token": teacher_token,
            "student_tokens": [],
            "student_voices": {},
            "student_names": {},
            "student_genders": {},
            "status": "live",
            "segments": [],
            "cues": [],
            "student_upload_until": {},
            "created_at": time.time(),
            "ended_at": None,
            "lesson_id": "",
            "lesson_token": "",
        }
        created = lessons.create_lesson(class_id=room["id"], teacher_token=teacher_token)
        lessons.bind_room_lesson(room, created["lesson_id"], created["lesson_token"])
        _BOARD["rooms"].append(room)
        _persist_unlocked()
        return {
            "class_id": room["id"],
            "join_code": code,
            "teacher_token": room["teacher_token"],
            "lesson_id": created["lesson_id"],
            "lesson_token": created["lesson_token"],
            "status": "live",
        }


def join_class(
    join_code: str,
    voice: str = "",
    display_name: str = "",
    gender: str = "",
) -> dict[str, str]:
    code = "".join(ch for ch in join_code if ch.isdigit())
    chosen = parse_voice(voice) or DEFAULT_VOICE
    name = sanitize_display_name(display_name)
    if not name:
        raise ClassError(400, "name_required")
    speaker = parse_gender(gender) or DEFAULT_GENDER
    with _LOCK:
        _load_unlocked()
        room = _room_by_code_unlocked(code)
        if room is None or room["status"] != "live":
            raise ClassError(404, "not_found")
        token = secrets.token_urlsafe(24)
        room["student_tokens"].append(token)
        voices = room.get("student_voices")
        if not isinstance(voices, dict):
            voices = {}
            room["student_voices"] = voices
        voices[token] = chosen
        names = room.get("student_names")
        if not isinstance(names, dict):
            names = {}
            room["student_names"] = names
        names[token] = name
        genders = room.get("student_genders")
        if not isinstance(genders, dict):
            genders = {}
            room["student_genders"] = genders
        genders[token] = speaker
        _persist_unlocked()
        return {
            "class_id": room["id"],
            "student_token": token,
            "status": room["status"],
            "voice": chosen,
            "display_name": name,
            "gender": speaker,
        }


def set_student_voice(token: str, voice: str) -> dict[str, str]:
    chosen = parse_voice(voice)
    if chosen is None:
        raise ValueError("Voice is not supported.")
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        if token not in room["student_tokens"]:
            raise ClassError(403, "not_student")
        if room["status"] != "live":
            raise ClassError(409, "ended")
        voices = room.get("student_voices")
        if not isinstance(voices, dict):
            voices = {}
            room["student_voices"] = voices
        voices[token] = chosen
        _persist_unlocked()
    return {"status": "ok", "voice": chosen}


@dataclass(frozen=True)
class LineOrder:
    """Teacher-side utterance order. Lines can finish out of order; listeners sort by seq."""

    seq: int
    wait_for: tuple[int, ...] = ()


def parse_line_order(seq_value: str, wait_value: str) -> LineOrder | None:
    seq_text = seq_value.strip()
    if not seq_text.isdigit() or len(seq_text) > 7:
        return None
    seq = int(seq_text)
    if seq < 1 or seq > _MAX_SEQ:
        return None
    waits: list[int] = []
    for part in wait_value.split(",")[: _MAX_WAIT_FOR * 2]:
        text = part.strip()
        if not text.isdigit() or len(text) > 7:
            continue
        value = int(text)
        if 1 <= value < seq and value not in waits:
            waits.append(value)
        if len(waits) >= _MAX_WAIT_FOR:
            break
    return LineOrder(seq=seq, wait_for=tuple(sorted(waits)))


def _as_context(items: Sequence[object]) -> list[ContextLine]:
    lines: list[ContextLine] = []
    for item in items:
        if isinstance(item, ContextLine):
            lines.append(item)
        elif isinstance(item, ContextLineIn):
            lines.append(ContextLine(item.english, item.spanish))
        elif isinstance(item, dict):
            lines.append(
                ContextLine(str(item.get("english") or ""), str(item.get("spanish") or ""))
            )
    return bound_context(lines)


def _skipped(reason: str, audience: str, order: LineOrder | None = None) -> dict[str, object]:
    return {
        "status": "skipped",
        "reason": reason,
        "audience": audience,
        "segment_id": "",
        "seq": order.seq if order else None,
        "english_text": "",
        "audio_available": False,
        "simulated": False,
        "delivered": False,
    }


def _class_phrase(
    settings: Settings,
    text: str,
    source: str,
    target: str,
    context: Sequence[ContextLine],
    mode: str,
    *,
    include_audio: bool,
) -> Interpretation:
    if is_filler_only(text):
        live = settings.provider_mode.strip().lower() == "live"
        return Interpretation("", "", "skipped", simulated=not live)
    if settings.provider_mode.strip().lower() != "live":
        result = interpret_text(settings, text, source, target, include_audio=include_audio)
        return Interpretation(
            translated_text=str(result["translated_text"]),
            clean_source=text,
            method="verbatim",
            simulated=bool(result.get("simulated")),
            audio_base64=str(result.get("audio_base64") or ""),
            audio_content_type=str(result.get("audio_content_type") or ""),
        )
    return interpret_phrase(
        settings,
        text,
        source,
        target,
        context=context,
        mode=parse_mode(mode),
        include_clean_source=True,
        translate=interpret_text,
    )


def _voices_in_use_unlocked(room: dict[str, Any]) -> list[VoiceId]:
    assigned = room.get("student_voices")
    tokens = room.get("student_tokens") if isinstance(room.get("student_tokens"), list) else []
    found: set[str] = set()
    if isinstance(assigned, dict):
        for token in tokens:
            if isinstance(token, str):
                found.add(parse_voice(assigned.get(token)) or DEFAULT_VOICE)
    if not found:
        found.add(DEFAULT_VOICE)
    return [voice_id for voice_id in VOICE_IDS if voice_id in found]


def _voices_for_token(token: str) -> list[VoiceId]:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            return [DEFAULT_VOICE]
        return _voices_in_use_unlocked(room)


def _voice_for_token_unlocked(room: dict[str, Any], token: str) -> VoiceId:
    assigned = room.get("student_voices")
    if isinstance(assigned, dict):
        return parse_voice(assigned.get(token)) or DEFAULT_VOICE
    return DEFAULT_VOICE


def _clip_for(item: dict[str, Any], voice: VoiceId) -> tuple[str, str]:
    """Return this listener's clip, or any finished clip if their voice was not ready yet.

    A student who joins while a line is still being spoken can miss their chosen voice on
    that line. Prefer their voice, then the default voice, then any stored clip, then the
    legacy single-clip fields. Never leave a ready line silent when another voice exists.
    """
    clips = item.get("clips")
    if isinstance(clips, dict):
        for key in (voice, DEFAULT_VOICE):
            chosen = clips.get(key)
            if isinstance(chosen, dict) and chosen.get("audio_base64"):
                kind = str(chosen.get("audio_content_type") or "audio/mpeg")
                return str(chosen["audio_base64"]), kind
        for chosen in clips.values():
            if isinstance(chosen, dict) and chosen.get("audio_base64"):
                kind = str(chosen.get("audio_content_type") or "audio/mpeg")
                return str(chosen["audio_base64"]), kind
    base = str(item.get("audio_base64") or "")
    if base:
        return base, str(item.get("audio_content_type") or "audio/mpeg")
    return "", ""


def post_line(
    token: str,
    settings: Settings,
    text: str,
    order: LineOrder | None = None,
    context: Sequence[object] = (),
    mode: str = "clean",
) -> dict[str, object]:
    with timing.stage("auth"):
        _require_live_teacher(token)
    return _publish_line(token, settings, text, order, _as_context(context), parse_mode(mode))


def say_next_lines(
    token: str,
    settings: Settings,
    context: Sequence[object] = (),
) -> dict[str, object]:
    """Three tap-to-send English suggestions for the teacher. Does not post a class line."""
    with timing.stage("auth"):
        _require_live_teacher(token)
    with timing.stage("say_next"):
        return suggest_next(settings, _as_context(context))


def _publish_line(
    token: str,
    settings: Settings,
    text: str,
    order: LineOrder | None,
    context: Sequence[ContextLine] = (),
    mode: str = "clean",
) -> dict[str, object]:
    """Translate once, publish the caption, then attach one clip per voice in use."""
    phrase = _class_phrase(settings, text, "en", "es", context, mode, include_audio=False)
    if phrase.skipped:
        return _skipped("filler", "students", order)
    live_audio = settings.provider_mode.strip().lower() == "live" and bool(
        settings.openai_tts_model.strip()
    )
    interpreted = phrase.as_result()
    english = phrase.clean_source or text
    if not live_audio:
        spoken = interpret_text(settings, text, "en", "es", include_audio=True)
        interpreted["translated_text"] = spoken["translated_text"]
        interpreted["audio_base64"] = spoken.get("audio_base64") or ""
        interpreted["audio_content_type"] = spoken.get("audio_content_type") or ""
        interpreted["simulated"] = bool(spoken.get("simulated"))
        segment = _new_segment(interpreted, order, english_text=english)
        clip = str(interpreted.get("audio_base64") or "")
        if clip:
            segment["audio_base64"] = clip
            segment["audio_content_type"] = str(interpreted.get("audio_content_type") or "")
        segment["audio_state"] = "ready" if clip else "none"
        segment["ready_ns"] = time.time_ns()
        _append_segment(token, segment)
        return _line_result(segment, english)
    segment = _new_segment(interpreted, order, english_text=english)
    timer = timing.current()
    started = time.perf_counter()
    # Read voices immediately before TTS so a student who just joined is included.
    voices = _voices_for_token(token)
    if DEFAULT_VOICE not in voices:
        voices = [*voices, DEFAULT_VOICE]
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=min(4, max(1, len(voices))), thread_name_prefix="bb-tts"
    )
    try:
        jobs = {
            voice_id: pool.submit(
                synthesize_line,
                settings,
                str(segment["spanish_text"]),
                "es",
                provider_voice=class_voice(voice_id).provider_voice,
                instructions=class_voice(voice_id).instructions,
            )
            for voice_id in voices
        }
        with timing.stage("caption_publish"):
            _append_segment(token, segment)
        clips: dict[str, dict[str, str]] = {}
        for voice_id, future in jobs.items():
            try:
                audio = future.result(timeout=45.0)
            except (concurrent.futures.TimeoutError, RuntimeError):
                audio = None
            if audio is not None:
                clips[voice_id] = {
                    "audio_base64": audio[0],
                    "audio_content_type": audio[1],
                }
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    if timer is not None:
        timer.add("tts_ready", round((time.perf_counter() - started) * 1000))
    chosen = clips.get(DEFAULT_VOICE) or next(iter(clips.values()), None)
    if chosen is not None:
        segment["audio_base64"] = chosen["audio_base64"]
        segment["audio_content_type"] = chosen["audio_content_type"]
        segment["audio_state"] = "ready"
        audio_bytes = sum(len(item["audio_base64"]) * 3 // 4 for item in clips.values())
        timing.record_size("audio_out", audio_bytes)
    else:
        segment["audio_state"] = "none"
    segment["clips"] = clips
    segment["ready_ns"] = time.time_ns()
    with timing.stage("audio_publish"):
        _finish_segment(token, segment)
    return _line_result(segment, phrase.clean_source or text)


def _new_segment(
    interpreted: dict[str, object],
    order: LineOrder | None,
    english_text: str = "",
) -> dict[str, Any]:
    return {
        "id": secrets.token_urlsafe(8),
        "english_text": " ".join(english_text.split())[:800],
        "spanish_text": str(interpreted["translated_text"]),
        "audio_base64": "",
        "audio_content_type": "",
        "simulated": bool(interpreted.get("simulated")),
        "audio_state": board_merge.PENDING_AUDIO,
        "appended_ns": time.time_ns(),
        "ready_ns": 0,
        "seq": order.seq if order else None,
        "wait_for": list(order.wait_for) if order else [],
        "clips": {},
    }


def _line_result(segment: dict[str, Any], english_text: str = "") -> dict[str, object]:
    return {
        "status": "live",
        "segment_id": segment["id"],
        "seq": segment.get("seq"),
        "spanish_text": segment["spanish_text"],
        "english_text": english_text,
        "audio_available": bool(segment["audio_base64"]),
        "audio_base64": segment["audio_base64"],
        "audio_content_type": segment["audio_content_type"],
        "simulated": segment["simulated"],
    }


def _append_segment(token: str, segment: dict[str, Any]) -> None:
    lesson_id = ""
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None or room["status"] != "live":
            raise ClassError(409, "ended")
        room["segments"].append(dict(segment))
        lesson_id = str(room.get("lesson_id") or "")
        _trim_room_unlocked(room)
        _persist_unlocked()
    _mirror_lesson_segment(lesson_id, segment)


def _finish_segment(token: str, segment: dict[str, Any]) -> None:
    """Store the finished segment. One bounded retry when the board store is unavailable."""
    for attempt in range(2):
        try:
            lesson_id = ""
            with _LOCK:
                _load_unlocked()
                room = _room_by_token_unlocked(token)
                if room is None or room["status"] != "live":
                    return
                segments = room["segments"]
                index = next(
                    (i for i, item in enumerate(segments) if item.get("id") == segment["id"]),
                    None,
                )
                if index is None:
                    segments.append(dict(segment))
                else:
                    segments[index] = dict(segment)
                lesson_id = str(room.get("lesson_id") or "")
                _trim_room_unlocked(room)
                _persist_unlocked()
            _mirror_lesson_segment(lesson_id, segment)
            return
        except ClassError as exc:
            if exc.status_code != 503 or attempt == 1:
                raise


def _mirror_lesson_segment(lesson_id: str, segment: dict[str, Any]) -> None:
    if not lesson_id:
        return
    seq = segment.get("seq")
    lessons.record_segment(
        lesson_id,
        segment_id=str(segment.get("id") or ""),
        seq=seq if isinstance(seq, int) else None,
        english=str(segment.get("english_text") or ""),
        spanish=str(segment.get("spanish_text") or ""),
        status="delivered" if segment.get("spanish_text") else "recognized",
        simulated=bool(segment.get("simulated")),
    )


def _trim_room_unlocked(room: dict[str, Any]) -> None:
    segments = board_merge.merge_items([], room.get("segments"))[-_MAX_SEGMENTS:]
    kept = 0
    for item in reversed(segments):
        clips = item.get("clips") if isinstance(item.get("clips"), dict) else {}
        count = len(clips) if clips else (1 if item.get("audio_base64") else 0)
        if kept > 0 and kept + count > _MAX_CLIPS:
            item["audio_base64"] = ""
            item["audio_content_type"] = ""
            item["clips"] = {}
            if item.get("audio_state") == "ready":
                item["audio_state"] = "expired"
        else:
            kept += count
    room["segments"] = segments
    cues = room.get("cues")
    if isinstance(cues, list) and len(cues) > _MAX_SEGMENTS:
        room["cues"] = cues[-_MAX_SEGMENTS:]


def _ns(value: object) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def feed(
    token: str,
    after: str,
    version: int = 1,
    have: str = "",
    first: bool = False,
) -> dict[str, object]:
    with _LOCK:
        _load_unlocked(max_age=_FEED_CACHE_SECONDS)
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        status = str(room["status"])
        segments = [dict(item) for item in room["segments"]]
        voice = _voice_for_token_unlocked(room, token)
    if version >= 2:
        return {
            "status": status,
            "version": 2,
            "segments": _feed_v2(segments, have, first, voice),
        }
    # Pages loaded before ordered delivery expect finished lines in completion order.
    ready = [item for item in segments if item.get("audio_state") != board_merge.PENDING_AUDIO]
    ready.sort(key=lambda item: _ns(item.get("ready_ns")))
    if after:
        index = next((i for i, item in enumerate(ready) if item["id"] == after), None)
        ready = ready[index + 1 :] if index is not None else ready
    return {
        "status": status,
        "segments": [
            {
                "id": item["id"],
                "spanish_text": item["spanish_text"],
                "audio_base64": _clip_for(item, voice)[0],
                "audio_content_type": _clip_for(item, voice)[1],
                "simulated": item["simulated"],
            }
            for item in ready
        ],
    }


def _feed_v2(
    segments: list[dict[str, Any]], have: str, first: bool, voice: VoiceId = DEFAULT_VOICE
) -> list[dict[str, object]]:
    """Captions for lines this listener lacks. Audio only for new finished lines.

    The first poll after joining returns the caption history without audio, so a late
    listener never replays old speech.
    """
    known = {part for part in have.split(",")[:64] if 0 < len(part) <= 32}
    delivered: list[dict[str, object]] = []
    for item in segments:
        if item["id"] in known:
            continue
        state = str(item.get("audio_state") or ("ready" if item.get("audio_base64") else "none"))
        entry: dict[str, object] = {
            "id": item["id"],
            "seq": item.get("seq"),
            "wait_for": item.get("wait_for") or [],
            "spanish_text": item["spanish_text"],
            "audio_state": state,
            "simulated": bool(item.get("simulated")),
        }
        clip, content_type = _clip_for(item, voice)
        if not first and state == "ready" and clip:
            entry["audio_base64"] = clip
            entry["audio_content_type"] = content_type
        delivered.append(entry)
    return delivered


def end_class(token: str) -> dict[str, str]:
    lesson_id = ""
    lesson_token = ""
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        if token != room["teacher_token"]:
            raise ClassError(403, "not_teacher")
        lesson_id = str(room.get("lesson_id") or "")
        lesson_token = str(room.get("lesson_token") or "")
        room["status"] = "ended"
        room["ended_at"] = time.time()
        room["segments"] = []
        room["cues"] = []
        room["student_voices"] = {}
        room["student_names"] = {}
        room["student_genders"] = {}
        room["student_upload_until"] = {}
        room["student_turn_until"] = None
        _persist_unlocked()
    result: dict[str, str] = {"status": "ended"}
    if lesson_id:
        try:
            finalized = lessons.finalize_lesson(lesson_id)
            result["lesson_id"] = finalized["lesson_id"]
            result["lesson_token"] = finalized["lesson_token"] or lesson_token
        except ClassError:
            if lesson_token:
                result["lesson_id"] = lesson_id
                result["lesson_token"] = lesson_token
    return result


_REHEARSAL_INTRO = (
    "Rehearsal. This is not a class recording. The voice is AI-generated. "
    "Greet the class and say: Peace be with you."
)
_REHEARSAL_REPLY_ES = "Gracias. La paz también esté contigo."


def post_teacher_audio(
    token: str,
    settings: Settings,
    audio: bytes,
    content_type: str,
    order: LineOrder | None = None,
    context: Sequence[object] = (),
    mode: str = "clean",
) -> dict[str, object]:
    with timing.stage("auth"):
        _require_live_teacher(token)
    lines = _as_context(context)
    recent = [line.english for line in lines if line.english]
    languages: list[str] = []
    transcript = transcribe_audio(
        settings,
        audio,
        content_type,
        languages_out=languages,
        prompt=transcription_prompt(recent) if recent else "",
    )
    if heard_only_spanish(languages):
        # Spanish on the teacher microphone is usually a student phone speaker replaying
        # the class voice. Publishing it again would repeat lines in a loop.
        return _skipped("not_english", "students", order)
    result = _publish_line(token, settings, transcript, order, lines, parse_mode(mode))
    if not result.get("english_text"):
        result["english_text"] = transcript
    result["audience"] = "students"
    return result


def heard_only_spanish(languages: list[str]) -> bool:
    if not languages:
        return False
    return all(code == "spa" or code.split("-", 1)[0] == "es" for code in languages)


def post_student_audio(
    token: str,
    settings: Settings,
    audio: bytes,
    content_type: str,
    context: Sequence[object] = (),
    mode: str = "clean",
) -> dict[str, object]:
    # Per-student lock only. Other students may leave questions at the same time.
    _claim_student_upload(token)
    try:
        lines = _as_context(context)
        recent = [line.spanish for line in lines if line.spanish]
        transcript = transcribe_audio(
            settings,
            audio,
            content_type,
            prompt=transcription_prompt(recent) if recent else "",
        )
        live = settings.provider_mode.strip().lower() == "live"
        phrase = _class_phrase(
            settings,
            transcript,
            "es",
            "en",
            lines,
            mode,
            include_audio=not live,
        )
        if phrase.skipped:
            _release_student_upload(token)
            return _skipped("filler", "teacher")
        english = phrase.translated_text
        audio_b64 = phrase.audio_base64
        audio_type = phrase.audio_content_type
        speaker = _gender_for_token(token)
        if live and not audio_b64:
            try:
                reply = gender_reply_voice(speaker)
                audio_b64, audio_type = synthesize_speech(
                    settings,
                    english,
                    "en",
                    provider_voice=reply.provider_voice,
                    instructions=reply.instructions,
                )
            except RuntimeError:
                audio_b64, audio_type = "", ""
        cue = {
            "id": secrets.token_urlsafe(8),
            "english_text": english,
            "audio_base64": audio_b64,
            "audio_content_type": audio_type,
            "simulated": phrase.simulated,
            "kind": "student_reply",
            "student_name": _name_for_token(token),
            "speaker_gender": speaker,
            "listened": False,
            "created_at": time.time(),
            "appended_ns": time.time_ns(),
        }
        # One snapshot write stores the English question and clears this student's upload lock.
        _commit_student_cue(token, cue)
    except Exception:
        _release_student_upload(token)
        raise
    return {"status": "ok", "delivered": True, "audience": "teacher"}


def teacher_cues(token: str, after: str = "") -> dict[str, object]:
    """Return every student question for this class so the teacher can replay any of them.

    List payloads omit audio so the inbox stays small. Fetch one question to play it.
    """
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        if token != room["teacher_token"]:
            raise ClassError(403, "not_teacher")
        cues = _cue_list(room)
        listed = [_cue_public(item, include_audio=False) for item in cues]
        if after:
            index = next((i for i, item in enumerate(listed) if item["id"] == after), None)
            fresh = listed[index + 1 :] if index is not None else listed
        else:
            fresh = listed
        unread = sum(1 for item in listed if not item.get("listened"))
        return {
            "status": room["status"],
            "listener_count": len(room.get("student_tokens", [])),
            "unread_count": unread,
            "cues": listed,
            "new_cues": fresh,
        }


def get_question(token: str, cue_id: str) -> dict[str, object]:
    """Return one student question with English audio for teacher playback."""
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        if token != room["teacher_token"]:
            raise ClassError(403, "not_teacher")
        for item in _cue_list(room):
            if item.get("id") == cue_id:
                return {"status": "ok", "cue": _cue_public(item, include_audio=True)}
        raise ClassError(404, "not_found")


def mark_question_heard(token: str, cue_id: str) -> dict[str, object]:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        if token != room["teacher_token"]:
            raise ClassError(403, "not_teacher")
        if room["status"] != "live":
            raise ClassError(409, "ended")
        cues = _cue_list(room)
        for item in cues:
            if item.get("id") == cue_id:
                item["listened"] = True
                _persist_unlocked()
                unread = sum(1 for cue in cues if not cue.get("listened"))
                return {"status": "ok", "id": cue_id, "unread_count": unread}
        raise ClassError(404, "not_found")


def rehearsal_step(
    token: str,
    settings: Settings,
    step: str,
    spanish_text: str,
) -> dict[str, object]:
    _require_live_teacher(token)
    if step == "intro":
        spoken = _REHEARSAL_INTRO
    elif step == "explain":
        line = " ".join(spanish_text.split())
        if not line:
            raise ValueError("Spanish line is empty.")
        spoken = (
            "The students receive this Spanish line: "
            f"{line[:400]} The voice is AI-generated. This rehearsal is not a recording."
        )
    elif step == "reply":
        interpreted = interpret_text(settings, _REHEARSAL_REPLY_ES, "es", "en", include_audio=False)
        english = str(interpreted["translated_text"])
        spoken = f"Rehearsal reply, not a live student. In English: {english}"
    else:
        raise ValueError("Rehearsal step is not supported.")
    result: dict[str, object] = {
        "status": "ok",
        "audience": "teacher",
        "rehearsal": True,
        "text": spoken,
        "audio_available": False,
        "simulated": settings.provider_mode.strip().lower() != "live",
    }
    if settings.provider_mode.strip().lower() == "live":
        encoded, content_type = synthesize_speech(settings, spoken, "en")
        result["audio_available"] = True
        result["audio_base64"] = encoded
        result["audio_content_type"] = content_type
        result["simulated"] = False
    return result


def _require_live_teacher(token: str) -> None:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        if token != room["teacher_token"]:
            raise ClassError(403, "not_teacher")
        if room["status"] != "live":
            raise ClassError(409, "ended")


def _claim_student_upload(token: str) -> None:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            raise ClassError(404, "not_found")
        if token not in room["student_tokens"]:
            raise ClassError(403, "not_student")
        if room["status"] != "live":
            raise ClassError(409, "ended")
        locks = room.get("student_upload_until")
        if not isinstance(locks, dict):
            locks = {}
            room["student_upload_until"] = locks
        until = locks.get(token)
        if isinstance(until, int | float) and until > time.time():
            raise ClassError(409, "busy")
        locks[token] = time.time() + 45
        _persist_unlocked()


def _release_student_upload(token: str) -> None:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None or token not in room.get("student_tokens", []):
            return
        locks = room.get("student_upload_until")
        if isinstance(locks, dict):
            locks.pop(token, None)
            _persist_unlocked()


def _commit_student_cue(token: str, cue: dict[str, object]) -> None:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None or token not in room.get("student_tokens", []):
            raise ClassError(403, "not_student")
        if room["status"] != "live":
            raise ClassError(409, "ended")
        if not cue.get("student_name"):
            names = room.get("student_names")
            if isinstance(names, dict):
                cue["student_name"] = sanitize_display_name(names.get(token)) or "Student"
            else:
                cue["student_name"] = "Student"
        cues = _cue_list(room)
        cues.append(cue)
        if len(cues) > _MAX_SEGMENTS:
            room["cues"] = cues[-_MAX_SEGMENTS:]
        locks = room.get("student_upload_until")
        if isinstance(locks, dict):
            locks.pop(token, None)
        _persist_unlocked()


def _name_for_token(token: str) -> str:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            return "Student"
        names = room.get("student_names")
        if isinstance(names, dict):
            return sanitize_display_name(names.get(token)) or "Student"
        return "Student"


def _gender_for_token(token: str) -> SpeakerGender:
    with _LOCK:
        _load_unlocked()
        room = _room_by_token_unlocked(token)
        if room is None:
            return DEFAULT_GENDER
        genders = room.get("student_genders")
        if isinstance(genders, dict):
            return parse_gender(genders.get(token)) or DEFAULT_GENDER
        return DEFAULT_GENDER


def _cue_public(item: dict[str, Any], *, include_audio: bool = True) -> dict[str, object]:
    audio = str(item.get("audio_base64") or "")
    content_type = str(item.get("audio_content_type") or "")
    if audio and not content_type:
        content_type = "audio/mpeg"
    payload: dict[str, object] = {
        "id": item["id"],
        "english_text": item.get("english_text") or "",
        "simulated": bool(item.get("simulated")),
        "kind": item.get("kind") or "student_reply",
        "student_name": sanitize_display_name(item.get("student_name")) or "Student",
        "speaker_gender": parse_gender(item.get("speaker_gender")) or DEFAULT_GENDER,
        "listened": bool(item.get("listened")),
        "created_at": item.get("created_at") if isinstance(item.get("created_at"), int | float) else 0,
        "audio_available": bool(audio),
    }
    if include_audio and audio:
        payload["audio_base64"] = audio
        payload["audio_content_type"] = content_type
    return payload


def _cue_list(room: dict[str, Any]) -> list[dict[str, Any]]:
    cues = room.get("cues")
    if not isinstance(cues, list):
        fresh: list[dict[str, Any]] = []
        room["cues"] = fresh
        return fresh
    return cues


def _new_code_unlocked() -> str:
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if _room_by_code_unlocked(code) is None:
            return code
    raise ClassError(503, "unavailable")


def _room_by_code_unlocked(code: str) -> dict[str, Any] | None:
    rooms: list[dict[str, Any]] = _BOARD["rooms"]
    for room in rooms:
        if room["code"] == code and room["status"] == "live":
            return room
    return None


def _room_by_token_unlocked(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    rooms: list[dict[str, Any]] = _BOARD["rooms"]
    for room in rooms:
        if token == room["teacher_token"] or token in room["student_tokens"]:
            return room
    return None


def _purge_unlocked() -> None:
    now = time.time()
    kept = []
    for room in _BOARD["rooms"]:
        ended = room.get("ended_at")
        if isinstance(ended, int | float) and now - ended > _KEEP_AFTER_END_SECONDS:
            continue
        created = room.get("created_at")
        if room.get("status") == "live" and (
            not isinstance(created, int | float) or now - created > _KEEP_LIVE_SECONDS
        ):
            continue
        kept.append(room)
    _BOARD["rooms"] = kept


def _revision_of(payload: dict[str, Any]) -> int:
    value: object = payload.get("revision", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _load_unlocked(max_age: float = 0.0) -> None:
    global _LOADED, _LOADED_AT
    blob = bool(_blob_token())
    if _LOADED and not blob:
        return
    if blob and _LOADED and max_age > 0 and time.monotonic() - _LOADED_AT < max_age:
        return
    with timing.stage("board_read"):
        loaded = _read_blob() if blob else _read_file()
    if blob and loaded is None:
        raise ClassError(503, "unavailable")
    if loaded is None:
        _LOADED = True
        _LOADED_AT = time.monotonic()
        _purge_unlocked()
        return
    remote = _revision_of(loaded)
    local = _revision_of(_BOARD)
    if _LOADED:
        # A cached blob list can return the board from before this process stored the cue,
        # and another instance can store changes this process has not seen. Merge both so
        # neither the English cue audio nor another instance's line is dropped on save.
        mine = {"rooms": _BOARD["rooms"]}
        ordered = [loaded, mine] if remote < local else [mine, loaded]
        _BOARD["rooms"] = board_merge.merge_snapshots(ordered)["rooms"]
    else:
        _BOARD["rooms"] = board_merge.merge_snapshots([loaded])["rooms"]
    _BOARD["revision"] = max(remote, local)
    _LOADED = True
    _LOADED_AT = time.monotonic()
    for room in _BOARD["rooms"]:
        _trim_room_unlocked(room)
    _purge_unlocked()


def _persist_unlocked() -> None:
    global _LOADED_AT
    _BOARD["revision"] = _revision_of(_BOARD) + 1
    payload = {"revision": _BOARD["revision"], "rooms": _BOARD["rooms"]}
    with timing.stage("board_write"):
        _write_file(payload)
        _write_blob(payload)
    _LOADED_AT = time.monotonic()


def _file_path() -> Path:
    override = os.environ.get("BABELBEAM_CLASS_FILE", "").strip()
    if override:
        return Path(override)
    return Path(os.environ.get("TEMP", "/tmp")) / "babelbeam-class-board.json"


def _read_file() -> dict[str, Any] | None:
    path = _file_path()
    if not path.is_file():
        return None
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _write_file(payload: dict[str, Any]) -> None:
    path = _file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)


def _blob_token() -> str:
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()


def _blob_api_headers(token: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {token}",
        "x-api-version": "13",
    }


def _list_boards(token: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    cursor = ""
    for _ in range(5):
        params = {"prefix": _BLOB_PREFIX}
        if cursor:
            params["cursor"] = cursor
        response = httpx.get(
            "https://vercel.com/api/blob",
            params=params,
            headers=_blob_api_headers(token),
            timeout=10.0,
        )
        if response.status_code != 200:
            raise ClassError(503, "unavailable")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ClassError(503, "unavailable")
        blobs = payload.get("blobs")
        if isinstance(blobs, list):
            found.extend(item for item in blobs if isinstance(item, dict))
        if not payload.get("hasMore"):
            break
        cursor = str(payload.get("cursor") or "")
        if not cursor:
            break
    return found


def _read_blob() -> dict[str, Any] | None:
    """Merge the recent board snapshots. One bounded retry if every listed copy vanished."""
    token = _blob_token()
    if not token:
        return None
    for _attempt in range(2):
        try:
            blobs = _list_boards(token)
        except (httpx.HTTPError, json.JSONDecodeError, ClassError):
            return None
        boards = [
            item for item in blobs if str(item.get("pathname") or "").startswith(_BLOB_PREFIX)
        ]
        if not boards:
            _MERGED_PATHNAMES.clear()
            return {"revision": 0, "rooms": []}
        boards.sort(
            key=lambda item: (str(item.get("uploadedAt") or ""), str(item.get("pathname") or ""))
        )
        recent = boards[-_READ_LIMIT:]
        loaded = list(_IO_POOL.map(lambda item: _get_board(token, item), recent))
        snapshots: list[dict[str, Any]] = []
        pathnames: list[str] = []
        for item, snapshot in zip(recent, loaded, strict=True):
            if snapshot is not None:
                snapshots.append(snapshot)
                pathnames.append(str(item.get("pathname") or ""))
        if snapshots:
            merged = board_merge.merge_snapshots(snapshots)
            merged["revision"] = max(_revision_of(snapshot) for snapshot in snapshots)
            _MERGED_PATHNAMES[:] = pathnames
            return merged
    return None


def _get_board(token: str, item: dict[str, Any]) -> dict[str, Any] | None:
    target = str(item.get("downloadUrl") or item.get("url") or "")
    if not target:
        return None
    try:
        response = httpx.get(
            target,
            headers={"authorization": f"Bearer {token}"},
            timeout=10.0,
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        loaded: object = response.json()
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _write_blob(payload: dict[str, Any]) -> None:
    token = _blob_token()
    if not token:
        return
    pathname = f"{_BLOB_PREFIX}{time.time_ns()}-{secrets.token_hex(4)}.json"
    headers = _blob_api_headers(token)
    headers["x-content-type"] = "application/json"
    headers["x-add-random-suffix"] = "0"
    headers["x-allow-overwrite"] = "0"
    headers["x-vercel-blob-access"] = "private"
    headers["x-cache-control-max-age"] = "0"
    try:
        response = httpx.put(
            "https://vercel.com/api/blob/",
            params={"pathname": pathname},
            headers=headers,
            content=json.dumps(payload).encode("utf-8"),
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise ClassError(503, "unavailable") from exc
    if response.status_code not in {200, 201}:
        raise ClassError(503, "unavailable")
    merged = [name for name in _MERGED_PATHNAMES if name != pathname]
    _MERGED_PATHNAMES[:] = [pathname]
    _prune_boards(token, merged)


def _prune_boards(token: str, pathnames: list[str]) -> None:
    """Delete only snapshots whose content this process merged into the copy it just wrote.

    A snapshot another request wrote meanwhile is never deleted here, so concurrent writers
    cannot erase each other's classes. Deletes are best effort; leftovers merge on read.
    """
    if not pathnames:
        return
    with timing.stage("board_prune"):
        pending = [_IO_POOL.submit(_delete_pathname, token, name) for name in pathnames]
        concurrent.futures.wait(pending, timeout=_PRUNE_WAIT_SECONDS)


def _delete_pathname(token: str, pathname: str) -> None:
    try:
        httpx.delete(
            "https://vercel.com/api/blob",
            params={"pathname": pathname},
            headers=_blob_api_headers(token),
            timeout=10.0,
        )
    except httpx.HTTPError:
        return

"""Durable text-only lesson transcripts and teaching artifacts.

Live classroom audio is not stored. Recognition and delivered translation are kept
separately from AI lesson drafts. Failures here must not stop live translation.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from app.errors import ClassError

# RLock: _public_lesson may build course memory while a caller already holds the lock.
_LOCK = threading.RLock()
_LESSONS: dict[str, dict[str, Any]] = {}
_BLOB_PREFIX = "classroom/lessons/"
_MAX_SEGMENTS = 500
_MAX_CORRECTIONS = 200
_RETENTION_DAYS = 90
_SHARE_PREFIX = "bbshare_"

AugmentMode = str  # off | critical | light


def reset_lessons() -> None:
    with _LOCK:
        _LESSONS.clear()
        root = _lesson_dir()
        if root is not None and root.is_dir():
            for path in root.glob("*.json"):
                try:
                    path.unlink()
                except OSError:
                    pass


def create_lesson(*, class_id: str, teacher_token: str, course_id: str = "", course_title: str = "") -> dict[str, str]:
    lesson_id = secrets.token_urlsafe(12)
    access = secrets.token_urlsafe(24)
    now = time.time()
    lesson: dict[str, Any] = {
        "id": lesson_id,
        "class_id": class_id,
        "teacher_token": teacher_token,
        "access_token": access,
        "course_id": course_id.strip()[:64],
        "course_title": course_title.strip()[:120],
        "status": "live",
        "created_at": now,
        "ended_at": None,
        "segments": [],
        "corrections": [],
        "quality_notes": [],
        "gaps": [],
        "outline": {
            "status": "idle",
            "augmentation": "critical",
            "english": "",
            "spanish": "",
            "ai_additions": [],
            "citations": [],
            "revision": 0,
            "error": "",
            "generated_at": None,
        },
        "quiz": None,
        "publication": {
            "status": "private",
            "share_token": "",
            "include_transcript": False,
            "published_at": None,
            "revoked_at": None,
            "expires_at": None,
        },
        "retention_days": _RETENTION_DAYS,
    }
    with _LOCK:
        _LESSONS[lesson_id] = lesson
        _persist_unlocked(lesson)
    return {"lesson_id": lesson_id, "lesson_token": access}


def bind_room_lesson(room: dict[str, Any], lesson_id: str, lesson_token: str) -> None:
    room["lesson_id"] = lesson_id
    room["lesson_token"] = lesson_token


def record_segment(
    lesson_id: str,
    *,
    segment_id: str,
    seq: int | None,
    english: str,
    spanish: str,
    status: str = "delivered",
    simulated: bool = False,
) -> None:
    """Append or update one transcript segment. Best-effort; never raises into the class path."""
    try:
        with _LOCK:
            lesson = _LESSONS.get(lesson_id) or _load_one_unlocked(lesson_id)
            if lesson is None or lesson.get("status") == "deleted":
                return
            segments: list[dict[str, Any]] = lesson["segments"]
            index = next((i for i, item in enumerate(segments) if item.get("id") == segment_id), None)
            entry = {
                "id": segment_id,
                "seq": seq,
                "t": time.time(),
                "recognized_english": " ".join(english.split())[:800],
                "delivered_spanish": " ".join(spanish.split())[:800],
                "status": status,
                "simulated": simulated,
            }
            if index is None:
                segments.append(entry)
            else:
                # Keep original recognition; update delivered Spanish if it arrived later.
                prior = segments[index]
                entry["recognized_english"] = prior.get("recognized_english") or entry["recognized_english"]
                if not entry["delivered_spanish"]:
                    entry["delivered_spanish"] = prior.get("delivered_spanish") or ""
                segments[index] = entry
            if len(segments) > _MAX_SEGMENTS:
                lesson["gaps"].append(
                    {
                        "at": time.time(),
                        "reason": "segment_cap",
                        "dropped": len(segments) - _MAX_SEGMENTS,
                    }
                )
                lesson["segments"] = segments[-_MAX_SEGMENTS:]
            _persist_unlocked(lesson)
    except Exception:
        # Live class continues even if durable write fails.
        return


def mark_gap(lesson_id: str, reason: str) -> None:
    try:
        with _LOCK:
            lesson = _LESSONS.get(lesson_id) or _load_one_unlocked(lesson_id)
            if lesson is None:
                return
            lesson["gaps"].append({"at": time.time(), "reason": reason[:80]})
            _persist_unlocked(lesson)
    except Exception:
        return


def finalize_lesson(lesson_id: str) -> dict[str, str]:
    with _LOCK:
        lesson = _require_lesson_unlocked(lesson_id)
        lesson["status"] = "ended"
        lesson["ended_at"] = time.time()
        outline = lesson["outline"]
        if outline.get("status") in {"idle", "failed"}:
            outline["status"] = "queued"
        _persist_unlocked(lesson)
        return {
            "status": "ended",
            "lesson_id": lesson["id"],
            "lesson_token": lesson["access_token"],
        }


def get_lesson(access_token: str, lesson_id: str) -> dict[str, Any]:
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        return _public_lesson(lesson, teacher=True)


def list_recent_for_token(access_token: str, limit: int = 20) -> list[dict[str, object]]:
    with _LOCK:
        _load_all_unlocked()
        found: list[dict[str, Any]] = []
        for lesson in _LESSONS.values():
            if lesson.get("access_token") == access_token or lesson.get("teacher_token") == access_token:
                found.append(lesson)
        found.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
        return [
            {
                "id": item["id"],
                "status": item.get("status"),
                "created_at": item.get("created_at"),
                "ended_at": item.get("ended_at"),
                "course_title": item.get("course_title") or "",
                "segment_count": len(item.get("segments") or []),
                "outline_status": (item.get("outline") or {}).get("status"),
                "publication_status": (item.get("publication") or {}).get("status"),
            }
            for item in found[: max(1, min(limit, 50))]
        ]


def update_course(access_token: str, lesson_id: str, course_id: str, course_title: str) -> dict[str, Any]:
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        lesson["course_id"] = course_id.strip()[:64]
        lesson["course_title"] = course_title.strip()[:120]
        _persist_unlocked(lesson)
        return _public_lesson(lesson, teacher=True)


def add_correction(
    access_token: str,
    lesson_id: str,
    *,
    segment_id: str,
    language: str,
    corrected_text: str,
    reason: str = "",
) -> dict[str, Any]:
    language = language.strip().lower()
    if language not in {"en", "es"}:
        raise ClassError(400, "rejected")
    text = " ".join(corrected_text.split())[:800]
    if not text:
        raise ClassError(400, "rejected")
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        segment = next((item for item in lesson["segments"] if item.get("id") == segment_id), None)
        if segment is None:
            raise ClassError(404, "not_found")
        correction = {
            "id": secrets.token_urlsafe(8),
            "segment_id": segment_id,
            "language": language,
            "corrected_text": text,
            "reason": reason.strip()[:200],
            "at": time.time(),
        }
        lesson["corrections"].append(correction)
        lesson["corrections"] = lesson["corrections"][-_MAX_CORRECTIONS:]
        _persist_unlocked(lesson)
        return _public_lesson(lesson, teacher=True)


def add_quality_note(
    access_token: str,
    lesson_id: str,
    *,
    segment_id: str,
    rating: int,
    note: str = "",
) -> dict[str, Any]:
    if rating < 1 or rating > 5:
        raise ClassError(400, "rejected")
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        if not any(item.get("id") == segment_id for item in lesson["segments"]):
            raise ClassError(404, "not_found")
        lesson["quality_notes"].append(
            {
                "id": secrets.token_urlsafe(8),
                "segment_id": segment_id,
                "rating": rating,
                "note": note.strip()[:400],
                "at": time.time(),
            }
        )
        lesson["quality_notes"] = lesson["quality_notes"][-_MAX_CORRECTIONS:]
        _persist_unlocked(lesson)
        return _public_lesson(lesson, teacher=True)


def save_outline(
    access_token: str,
    lesson_id: str,
    *,
    english: str,
    spanish: str,
    ai_additions: list[dict[str, Any]] | None = None,
    approve: bool = False,
) -> dict[str, Any]:
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        outline = lesson["outline"]
        outline["english"] = english[:20000]
        outline["spanish"] = spanish[:20000]
        if ai_additions is not None:
            outline["ai_additions"] = ai_additions[:40]
        outline["revision"] = int(outline.get("revision") or 0) + 1
        outline["status"] = "approved" if approve else "draft"
        outline["error"] = ""
        _persist_unlocked(lesson)
        return _public_lesson(lesson, teacher=True)


def set_outline_status(lesson_id: str, status: str, **fields: Any) -> None:
    with _LOCK:
        lesson = _require_lesson_unlocked(lesson_id)
        outline = lesson["outline"]
        outline["status"] = status
        for key, value in fields.items():
            outline[key] = value
        _persist_unlocked(lesson)


def save_quiz(
    access_token: str,
    lesson_id: str,
    quiz: dict[str, Any],
    *,
    approve: bool = False,
) -> dict[str, Any]:
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        stored = dict(quiz)
        stored["status"] = "approved" if approve else "draft"
        stored["revision"] = int((lesson.get("quiz") or {}).get("revision") or 0) + 1
        stored["updated_at"] = time.time()
        lesson["quiz"] = stored
        _persist_unlocked(lesson)
        return _public_lesson(lesson, teacher=True)


def set_quiz_generating(lesson_id: str) -> None:
    with _LOCK:
        lesson = _require_lesson_unlocked(lesson_id)
        lesson["quiz"] = {
            "status": "generating",
            "english": "",
            "spanish": "",
            "items": [],
            "revision": int((lesson.get("quiz") or {}).get("revision") or 0),
            "error": "",
            "updated_at": time.time(),
        }
        _persist_unlocked(lesson)


def replace_quiz(lesson_id: str, quiz: dict[str, Any]) -> None:
    with _LOCK:
        lesson = _require_lesson_unlocked(lesson_id)
        lesson["quiz"] = quiz
        _persist_unlocked(lesson)


def publish_lesson(
    access_token: str,
    lesson_id: str,
    *,
    include_transcript: bool = False,
    expires_hours: int | None = None,
) -> dict[str, Any]:
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        outline = lesson.get("outline") or {}
        if outline.get("status") not in {"draft", "approved"} or not outline.get("english"):
            raise ClassError(409, "outline_required")
        pub = lesson["publication"]
        if not pub.get("share_token"):
            pub["share_token"] = f"{_SHARE_PREFIX}{secrets.token_urlsafe(18)}"
        pub["status"] = "published"
        pub["include_transcript"] = bool(include_transcript)
        pub["published_at"] = time.time()
        pub["revoked_at"] = None
        if expires_hours and expires_hours > 0:
            pub["expires_at"] = time.time() + expires_hours * 3600
        else:
            pub["expires_at"] = None
        _persist_unlocked(lesson)
        return _public_lesson(lesson, teacher=True)


def revoke_publication(access_token: str, lesson_id: str) -> dict[str, Any]:
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        pub = lesson["publication"]
        pub["status"] = "revoked"
        pub["revoked_at"] = time.time()
        _persist_unlocked(lesson)
        return _public_lesson(lesson, teacher=True)


def delete_lesson(access_token: str, lesson_id: str) -> dict[str, str]:
    with _LOCK:
        lesson = _require_access_unlocked(access_token, lesson_id)
        lesson["status"] = "deleted"
        lesson["segments"] = []
        lesson["corrections"] = []
        lesson["quality_notes"] = []
        lesson["outline"] = {
            "status": "idle",
            "augmentation": "critical",
            "english": "",
            "spanish": "",
            "ai_additions": [],
            "citations": [],
            "revision": 0,
            "error": "",
            "generated_at": None,
        }
        lesson["quiz"] = None
        pub = lesson["publication"]
        pub["status"] = "revoked"
        pub["revoked_at"] = time.time()
        pub["share_token"] = ""
        _persist_unlocked(lesson)
        return {"status": "deleted", "lesson_id": lesson_id}


def get_shared(share_token: str) -> dict[str, Any]:
    token = share_token.strip()
    if not token.startswith(_SHARE_PREFIX):
        raise ClassError(404, "not_found")
    with _LOCK:
        _load_all_unlocked()
        for lesson in _LESSONS.values():
            pub = lesson.get("publication") or {}
            if pub.get("share_token") != token:
                continue
            if pub.get("status") != "published":
                raise ClassError(404, "not_found")
            expires = pub.get("expires_at")
            if isinstance(expires, int | float) and expires < time.time():
                raise ClassError(404, "not_found")
            if lesson.get("status") == "deleted":
                raise ClassError(404, "not_found")
            return _public_shared(lesson)
        raise ClassError(404, "not_found")


def prior_approved_summaries(
    course_id: str,
    *,
    teacher_token: str = "",
    exclude_lesson_id: str = "",
    limit: int = 5,
) -> list[dict[str, str]]:
    """Return approved outlines for the same course id.

    Pilot classes mint a new teacher token each session, so continuity is keyed by
    course_id (set by the teacher), not teacher_token. teacher_token is accepted for
    call-site compatibility and reserved for a stricter tenant filter later.
    """
    _ = teacher_token
    if not course_id.strip():
        return []
    with _LOCK:
        _load_all_unlocked()
        matches = [
            lesson
            for lesson in _LESSONS.values()
            if lesson.get("course_id") == course_id
            and lesson.get("id") != exclude_lesson_id
            and lesson.get("status") != "deleted"
            and (lesson.get("outline") or {}).get("status") == "approved"
            and (lesson.get("outline") or {}).get("english")
        ]
        matches.sort(key=lambda item: float(item.get("ended_at") or item.get("created_at") or 0))
        out: list[dict[str, str]] = []
        for lesson in matches[-limit:]:
            outline = lesson["outline"]
            out.append(
                {
                    "lesson_id": lesson["id"],
                    "title": lesson.get("course_title") or "",
                    "ended_at": str(lesson.get("ended_at") or lesson.get("created_at") or ""),
                    "english": str(outline.get("english") or "")[:4000],
                }
            )
        return out


def course_history(
    course_id: str,
    *,
    teacher_token: str = "",
    exclude_lesson_id: str = "",
    limit: int = 12,
) -> list[dict[str, object]]:
    """Ordered lessons in the same course (continuity UI)."""
    _ = teacher_token
    if not course_id.strip():
        return []
    with _LOCK:
        _load_all_unlocked()
        matches = [
            lesson
            for lesson in _LESSONS.values()
            if lesson.get("course_id") == course_id
            and lesson.get("id") != exclude_lesson_id
            and lesson.get("status") != "deleted"
        ]
        matches.sort(key=lambda item: float(item.get("ended_at") or item.get("created_at") or 0))
        out: list[dict[str, object]] = []
        for lesson in matches[-limit:]:
            outline = lesson.get("outline") or {}
            out.append(
                {
                    "lesson_id": lesson["id"],
                    "course_title": lesson.get("course_title") or "",
                    "status": lesson.get("status"),
                    "created_at": lesson.get("created_at"),
                    "ended_at": lesson.get("ended_at"),
                    "segment_count": len(lesson.get("segments") or []),
                    "outline_status": outline.get("status"),
                    "has_access_token": bool(lesson.get("access_token")),
                }
            )
        return out


def queued_outline_lessons() -> list[str]:
    with _LOCK:
        _load_all_unlocked()
        return [
            lesson["id"]
            for lesson in _LESSONS.values()
            if (lesson.get("outline") or {}).get("status") == "queued"
        ]


def lesson_for_generation(lesson_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _LESSONS.get(lesson_id) or _load_one_unlocked(lesson_id)


def _public_lesson(lesson: dict[str, Any], *, teacher: bool) -> dict[str, Any]:
    pub = lesson.get("publication") or {}
    payload: dict[str, Any] = {
        "id": lesson["id"],
        "status": lesson.get("status"),
        "created_at": lesson.get("created_at"),
        "ended_at": lesson.get("ended_at"),
        "course_id": lesson.get("course_id") or "",
        "course_title": lesson.get("course_title") or "",
        "segments": lesson.get("segments") or [],
        "corrections": lesson.get("corrections") or [],
        "quality_notes": lesson.get("quality_notes") or [],
        "gaps": lesson.get("gaps") or [],
        "outline": lesson.get("outline") or {},
        "quiz": lesson.get("quiz"),
        "publication": {
            "status": pub.get("status"),
            "include_transcript": bool(pub.get("include_transcript")),
            "published_at": pub.get("published_at"),
            "revoked_at": pub.get("revoked_at"),
            "expires_at": pub.get("expires_at"),
            "share_path": f"/share/{pub['share_token']}" if pub.get("share_token") else "",
        },
        "retention_days": lesson.get("retention_days") or _RETENTION_DAYS,
    }
    if teacher:
        teacher_token = str(lesson.get("teacher_token") or "")
        course_id = str(lesson.get("course_id") or "")
        payload["course_memory"] = prior_approved_summaries(
            course_id,
            teacher_token=teacher_token,
            exclude_lesson_id=str(lesson.get("id") or ""),
            limit=5,
        )
        payload["course_history"] = course_history(
            course_id,
            teacher_token=teacher_token,
            exclude_lesson_id=str(lesson.get("id") or ""),
            limit=12,
        )
    if teacher:
        payload["lesson_token"] = lesson.get("access_token")
    return payload


def _public_shared(lesson: dict[str, Any]) -> dict[str, Any]:
    pub = lesson.get("publication") or {}
    outline = lesson.get("outline") or {}
    quiz = lesson.get("quiz")
    payload: dict[str, Any] = {
        "id": lesson["id"],
        "course_title": lesson.get("course_title") or "",
        "created_at": lesson.get("created_at"),
        "ended_at": lesson.get("ended_at"),
        "outline": {
            "english": outline.get("english") or "",
            "spanish": outline.get("spanish") or "",
            "ai_additions": outline.get("ai_additions") or [],
            "citations": outline.get("citations") or [],
        },
        "quiz": None,
        "transcript": None,
        "disclaimer": (
            "AI-assisted bilingual teaching material. Review with your instructor. "
            "Not a doctrinal authority."
        ),
    }
    if quiz and quiz.get("status") in {"draft", "approved"}:
        payload["quiz"] = {
            "english": quiz.get("english") or "",
            "spanish": quiz.get("spanish") or "",
            "items": quiz.get("items") or [],
        }
    if pub.get("include_transcript"):
        payload["transcript"] = [
            {
                "t": item.get("t"),
                "english": item.get("recognized_english") or "",
                "spanish": item.get("delivered_spanish") or "",
            }
            for item in (lesson.get("segments") or [])
        ]
    return payload


def _require_access_unlocked(access_token: str, lesson_id: str) -> dict[str, Any]:
    lesson = _require_lesson_unlocked(lesson_id)
    if access_token not in {lesson.get("access_token"), lesson.get("teacher_token")}:
        raise ClassError(403, "forbidden")
    if lesson.get("status") == "deleted":
        raise ClassError(404, "not_found")
    return lesson


def _require_lesson_unlocked(lesson_id: str) -> dict[str, Any]:
    lesson = _LESSONS.get(lesson_id) or _load_one_unlocked(lesson_id)
    if lesson is None:
        raise ClassError(404, "not_found")
    _LESSONS[lesson_id] = lesson
    return lesson


def _lesson_dir() -> Path | None:
    override = os.environ.get("BABELBEAM_LESSON_DIR", "").strip()
    if override:
        return Path(override)
    if _blob_token():
        return None
    return Path(os.environ.get("TEMP", "/tmp")) / "babelbeam-lessons"


def _persist_unlocked(lesson: dict[str, Any]) -> None:
    root = _lesson_dir()
    if root is not None:
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{lesson['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(lesson), encoding="utf-8")
        temporary.replace(path)
    _write_blob(lesson)


def _load_one_unlocked(lesson_id: str) -> dict[str, Any] | None:
    root = _lesson_dir()
    if root is not None:
        path = root / f"{lesson_id}.json"
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if isinstance(loaded, dict) and loaded.get("id") == lesson_id:
                _LESSONS[lesson_id] = loaded
                return loaded
    blob = _read_blob(lesson_id)
    if blob is not None:
        _LESSONS[lesson_id] = blob
    return blob


def _load_all_unlocked() -> None:
    root = _lesson_dir()
    if root is not None and root.is_dir():
        for path in root.glob("*.json"):
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(loaded, dict) and loaded.get("id"):
                _LESSONS[str(loaded["id"])] = loaded
        return
    # Blob index listing is best-effort for teacher list; individual GET still loads by id.
    token = _blob_token()
    if not token:
        return
    try:
        response = httpx.get(
            "https://vercel.com/api/blob",
            params={"prefix": _BLOB_PREFIX},
            headers=_blob_api_headers(token),
            timeout=10.0,
        )
    except httpx.HTTPError:
        return
    if response.status_code != 200:
        return
    payload = response.json()
    blobs = payload.get("blobs") if isinstance(payload, dict) else None
    if not isinstance(blobs, list):
        return
    for item in blobs[:80]:
        if not isinstance(item, dict):
            continue
        pathname = str(item.get("pathname") or "")
        if not pathname.startswith(_BLOB_PREFIX) or not pathname.endswith(".json"):
            continue
        lesson_id = pathname[len(_BLOB_PREFIX) : -5]
        if lesson_id and lesson_id not in _LESSONS:
            _load_one_unlocked(lesson_id)


def _blob_token() -> str:
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()


def _blob_api_headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}", "x-api-version": "13"}


def _write_blob(lesson: dict[str, Any]) -> None:
    token = _blob_token()
    if not token:
        return
    pathname = f"{_BLOB_PREFIX}{lesson['id']}.json"
    headers = _blob_api_headers(token)
    headers["x-content-type"] = "application/json"
    headers["x-add-random-suffix"] = "0"
    headers["x-allow-overwrite"] = "1"
    headers["x-vercel-blob-access"] = "private"
    headers["x-cache-control-max-age"] = "0"
    try:
        httpx.put(
            "https://vercel.com/api/blob/",
            params={"pathname": pathname},
            headers=headers,
            content=json.dumps(lesson).encode("utf-8"),
            timeout=15.0,
        )
    except httpx.HTTPError:
        return


def _read_blob(lesson_id: str) -> dict[str, Any] | None:
    token = _blob_token()
    if not token:
        return None
    pathname = f"{_BLOB_PREFIX}{lesson_id}.json"
    try:
        listed = httpx.get(
            "https://vercel.com/api/blob",
            params={"prefix": pathname},
            headers=_blob_api_headers(token),
            timeout=10.0,
        )
    except httpx.HTTPError:
        return None
    if listed.status_code != 200:
        return None
    payload = listed.json()
    blobs = payload.get("blobs") if isinstance(payload, dict) else None
    if not isinstance(blobs, list) or not blobs:
        return None
    item = blobs[0] if isinstance(blobs[0], dict) else None
    if item is None:
        return None
    target = str(item.get("downloadUrl") or item.get("url") or "")
    if not target:
        return None
    try:
        response = httpx.get(target, headers={"authorization": f"Bearer {token}"}, timeout=10.0)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        loaded = response.json()
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]

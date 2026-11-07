from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from app.classroom import reset_classes
from app.lessons import reset_lessons
from app.main import create_app
from babelbeam_runtime import Settings
from babelbeam_runtime.config import PLAN_PATH


def test_teacher_student_line_and_end(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.setenv("BABELBEAM_LESSON_DIR", str(tmp_path / "lessons"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    reset_classes()
    reset_lessons()
    settings = Settings(
        plan_path=PLAN_PATH,
        provider_mode="mock",
        openai_api_key="",
        _env_file=None,  # type: ignore[call-arg]
    )
    client = TestClient(create_app(settings))
    opened = client.post("/api/v1/classes")
    assert opened.status_code == 200
    body = opened.json()
    assert len(body["join_code"]) == 6
    assert body["join_code"].isdigit()
    teacher = {"X-Class-Token": body["teacher_token"]}

    joined = client.post("/api/v1/classes/join", json={"join_code": body["join_code"], "display_name": "Ana"})
    assert joined.status_code == 200
    student = {"X-Class-Token": joined.json()["student_token"]}
    present = client.get("/api/v1/classes/cues", headers=teacher)
    assert present.status_code == 200
    assert present.json()["listener_count"] == 1

    denied = client.post("/api/v1/classes/line", headers=student, json={"text": "Hello class."})
    assert denied.status_code == 403

    said = client.post("/api/v1/classes/line", headers=teacher, json={"text": "Peace be with you."})
    assert said.status_code == 200
    said_body = said.json()
    assert said_body["spanish_text"] == "[mock:es] Peace be with you."
    assert said_body["simulated"] is True

    heard = client.get("/api/v1/classes/feed", headers=student)
    assert heard.status_code == 200
    segments = heard.json()["segments"]
    assert segments[0]["spanish_text"] == "[mock:es] Peace be with you."
    assert "join_code" not in heard.text

    ended = client.post("/api/v1/classes/end", headers=teacher)
    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    again = client.post("/api/v1/classes/line", headers=teacher, json={"text": "More."})
    assert again.status_code == 409
    missing = client.post("/api/v1/classes/join", json={"join_code": body["join_code"], "display_name": "Ana"})
    assert missing.status_code == 404


def _open(tmp_path, monkeypatch) -> tuple[TestClient, dict[str, str], dict[str, str]]:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.setenv("BABELBEAM_LESSON_DIR", str(tmp_path / "lessons"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    reset_classes()
    reset_lessons()
    settings = Settings(
        plan_path=PLAN_PATH,
        provider_mode="mock",
        openai_api_key="",
        _env_file=None,  # type: ignore[call-arg]
    )
    client = TestClient(create_app(settings))
    opened = client.post("/api/v1/classes")
    teacher = {"X-Class-Token": opened.json()["teacher_token"]}
    joined = client.post(
        "/api/v1/classes/join",
        json={"join_code": opened.json()["join_code"], "display_name": "Ana"},
    )
    student = {"X-Class-Token": joined.json()["student_token"]}
    return client, teacher, student


def test_mock_audio_does_not_invent_a_transcript(tmp_path, monkeypatch) -> None:
    client, teacher, student = _open(tmp_path, monkeypatch)
    clip = b"x" * 500
    spoken = client.post(
        "/api/v1/classes/utterance",
        headers=teacher,
        files={"audio": ("speech.webm", clip, "audio/webm")},
    )
    assert spoken.status_code == 503
    heard = client.get("/api/v1/classes/feed", headers=student)
    assert heard.json()["segments"] == []


def test_teacher_audio_reaches_students_and_rehearsal_stays_with_teacher(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.classroom.transcribe_audio",
        lambda *_args, **_kwargs: "Peace be with you.",
    )
    client, teacher, student = _open(tmp_path, monkeypatch)
    clip = b"x" * 500
    spoken = client.post(
        "/api/v1/classes/utterance",
        headers=teacher,
        files={"audio": ("speech.webm", clip, "audio/webm")},
    )
    assert spoken.status_code == 200
    assert spoken.json()["spanish_text"] == "[mock:es] Peace be with you."
    assert spoken.json()["audience"] == "students"
    heard = client.get("/api/v1/classes/feed", headers=student)
    assert heard.json()["segments"][0]["spanish_text"] == "[mock:es] Peace be with you."

    intro = client.post("/api/v1/classes/rehearse", headers=teacher, json={"step": "intro"})
    assert intro.status_code == 200
    intro_body = intro.json()
    assert intro_body["audience"] == "teacher"
    assert intro_body["rehearsal"] is True
    assert "not a class recording" in intro_body["text"]
    student_again = client.get("/api/v1/classes/feed", headers=student)
    assert "Rehearsal" not in student_again.text
    denied = client.get("/api/v1/classes/cues", headers=student)
    assert denied.status_code == 403


def test_student_reply_is_english_for_the_teacher_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.classroom.transcribe_audio", lambda *_args, **_kwargs: "Gracias")
    client, teacher, student = _open(tmp_path, monkeypatch)
    clip = b"x" * 500
    blocked = client.post(
        "/api/v1/classes/student-utterance",
        headers=teacher,
        files={"audio": ("speech.webm", clip, "audio/webm")},
    )
    assert blocked.status_code == 403
    reply = client.post(
        "/api/v1/classes/student-utterance",
        headers=student,
        files={"audio": ("speech.webm", clip, "audio/webm")},
    )
    assert reply.status_code == 200
    assert reply.json()["delivered"] is True
    assert "audio_base64" not in reply.json()
    cues = client.get("/api/v1/classes/cues", headers=teacher)
    assert cues.status_code == 200
    assert cues.json()["cues"][0]["english_text"] == "[mock:en] Gracias"
    assert cues.json()["cues"][0]["student_name"] == "Ana"
    assert cues.json()["cues"][0]["listened"] is False
    assert cues.json()["unread_count"] == 1
    assert cues.json()["cues"][0].get("audio_available") is False
    assert "audio_base64" not in cues.json()["cues"][0]
    student_feed = client.get("/api/v1/classes/feed", headers=student)
    assert student_feed.json()["segments"] == []
    assert "Gracias" not in student_feed.text


def test_student_reply_audio_is_kept_for_the_teacher_only(tmp_path, monkeypatch) -> None:
    spanish_audio = base64.b64encode(b"spanish-class-mpeg").decode("ascii")
    english_audio = base64.b64encode(b"english-reply-mpeg").decode("ascii")
    snapshots: list[dict[str, object]] = []
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "blob-test")

    def write_blob(payload: dict[str, object]) -> None:
        snapshots.append(json.loads(json.dumps(payload)))

    def read_blob() -> dict[str, object]:
        if not snapshots:
            return {"revision": 0, "rooms": []}
        loaded = json.loads(json.dumps(snapshots[-1]))
        assert isinstance(loaded, dict)
        return loaded

    monkeypatch.setattr("app.classroom._write_blob", write_blob)
    monkeypatch.setattr("app.classroom._read_blob", read_blob)

    def fake_interpret(
        _settings: object,
        _text: str,
        source: str,
        target: str,
        include_audio: bool = False,
    ) -> dict[str, object]:
        english = (source, target) == ("es", "en")
        clip = english_audio if english else spanish_audio
        return {
            "translated_text": "Thank you" if english else "La paz sea contigo.",
            "audio_base64": clip if include_audio else "",
            "audio_content_type": "audio/mpeg" if include_audio else "",
            "simulated": False,
        }

    monkeypatch.setattr("app.classroom.transcribe_audio", lambda *_args, **_kwargs: "Gracias")
    monkeypatch.setattr("app.classroom.interpret_text", fake_interpret)
    reset_classes()
    settings = Settings(
        plan_path=PLAN_PATH,
        provider_mode="mock",
        openai_api_key="",
        _env_file=None,  # type: ignore[call-arg]
    )
    client = TestClient(create_app(settings))
    opened = client.post("/api/v1/classes")
    assert opened.status_code == 200
    opened_body = opened.json()
    teacher = {"X-Class-Token": opened_body["teacher_token"]}
    joined = client.post("/api/v1/classes/join", json={"join_code": opened_body["join_code"], "display_name": "Ana"})
    assert joined.status_code == 200
    student = {"X-Class-Token": joined.json()["student_token"]}
    said = client.post(
        "/api/v1/classes/line",
        headers=teacher,
        json={"text": "Peace be with you."},
    )
    assert said.status_code == 200
    assert said.json()["audio_base64"] == spanish_audio

    reply = client.post(
        "/api/v1/classes/student-utterance",
        headers=student,
        files={"audio": ("speech.webm", b"x" * 500, "audio/webm")},
    )
    assert reply.status_code == 200
    assert reply.json() == {"status": "ok", "delivered": True, "audience": "teacher"}
    assert english_audio not in reply.text
    assert "Thank you" not in reply.text

    cues = client.get("/api/v1/classes/cues", headers=teacher)
    assert cues.status_code == 200
    cue = cues.json()["cues"][0]
    assert cue["english_text"] == "Thank you"
    assert "audio_base64" not in cue
    assert cue["audio_available"] is True
    assert cue["kind"] == "student_reply"
    full = client.get(f"/api/v1/classes/questions/{cue['id']}", headers=teacher)
    assert full.status_code == 200
    assert full.json()["cue"]["audio_base64"] == english_audio
    assert full.json()["cue"]["audio_content_type"] == "audio/mpeg"
    denied = client.get("/api/v1/classes/cues", headers=student)
    assert denied.status_code == 403

    feed = client.get("/api/v1/classes/feed", headers=student)
    assert feed.status_code == 200
    assert feed.json()["segments"][0]["audio_base64"] == spanish_audio
    assert english_audio not in feed.text
    assert "Thank you" not in feed.text

    stale = json.loads(json.dumps(snapshots[-1]))
    assert isinstance(stale, dict)
    rooms = stale["rooms"]
    assert isinstance(rooms, list)
    for room in rooms:
        assert isinstance(room, dict)
        cues_saved = room.get("cues", [])
        assert isinstance(cues_saved, list)
        for item in cues_saved:
            assert isinstance(item, dict)
            item["audio_base64"] = ""
            item["audio_content_type"] = ""
    stale["revision"] = int(stale["revision"]) - 1

    def read_stale() -> dict[str, object]:
        return json.loads(json.dumps(stale))

    monkeypatch.setattr("app.classroom._read_blob", read_stale)
    again = client.post("/api/v1/classes/join", json={"join_code": opened_body["join_code"], "display_name": "Ana"})
    assert again.status_code == 200
    kept = client.get("/api/v1/classes/cues", headers=teacher)
    assert kept.status_code == 200
    assert kept.json()["cues"][0]["audio_available"] is True
    kept_id = kept.json()["cues"][0]["id"]
    kept_full = client.get(f"/api/v1/classes/questions/{kept_id}", headers=teacher)
    assert kept_full.json()["cue"]["audio_base64"] == english_audio
    assert kept_full.json()["cue"]["audio_content_type"] == "audio/mpeg"
    saved = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))
    assert saved["rooms"][0]["cues"][0]["audio_base64"] == english_audio

    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    from app import classroom

    classroom._LOADED = False
    reloaded = client.get("/api/v1/classes/cues", headers=teacher)
    assert reloaded.status_code == 200
    assert reloaded.json()["cues"][0]["english_text"] == "Thank you"
    assert reloaded.json()["cues"][0]["audio_available"] is True
    student_again = client.get("/api/v1/classes/feed", headers=student)
    assert english_audio not in student_again.text
    assert "Thank you" not in student_again.text


def test_filler_only_teacher_line_creates_no_segment(tmp_path, monkeypatch) -> None:
    client, teacher, student = _open(tmp_path, monkeypatch)
    skipped = client.post("/api/v1/classes/line", headers=teacher, json={"text": "Um"})
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    assert skipped.json()["reason"] == "filler"
    heard = client.get("/api/v1/classes/feed", headers=student)
    assert heard.json()["segments"] == []


def test_student_voice_is_registered_and_unknown_ids_are_rejected(tmp_path, monkeypatch) -> None:
    client, teacher, student = _open(tmp_path, monkeypatch)
    opened = client.post("/api/v1/classes")
    joined = client.post(
        "/api/v1/classes/join",
        json={"join_code": opened.json()["join_code"], "voice": "felipe", "display_name": "Ana"},
    )
    assert joined.status_code == 200
    assert joined.json()["voice"] == "felipe"
    token = {"X-Class-Token": joined.json()["student_token"]}
    changed = client.post("/api/v1/classes/voice", headers=token, json={"voice": "mateo"})
    assert changed.status_code == 200
    assert changed.json()["voice"] == "mateo"
    rejected = client.post("/api/v1/classes/voice", headers=token, json={"voice": "marin"})
    assert rejected.status_code == 400
    teacher_voice = client.post("/api/v1/classes/voice", headers=teacher, json={"voice": "roberta"})
    assert teacher_voice.status_code == 403

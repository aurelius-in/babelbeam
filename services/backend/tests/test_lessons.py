from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.classroom import reset_classes
from app.lessons import reset_lessons
from app.main import create_app
from babelbeam_runtime import Settings
from babelbeam_runtime.config import PLAN_PATH


def _client(tmp_path, monkeypatch) -> TestClient:
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
    return TestClient(create_app(settings))


def test_transcript_survives_end_and_outline_draft(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    opened = client.post("/api/v1/classes").json()
    teacher = {"X-Class-Token": opened["teacher_token"]}
    assert opened["lesson_id"]
    assert opened["lesson_token"]

    said = client.post(
        "/api/v1/classes/line",
        headers=teacher,
        json={"text": "Today we will talk about baptism."},
    )
    assert said.status_code == 200

    ended = client.post("/api/v1/classes/end", headers=teacher)
    assert ended.status_code == 200
    body = ended.json()
    assert body["status"] == "ended"
    assert body["lesson_id"] == opened["lesson_id"]
    lesson_headers = {"X-Lesson-Token": body["lesson_token"]}

    lesson = client.get(f"/api/v1/lessons/{body['lesson_id']}", headers=lesson_headers)
    assert lesson.status_code == 200
    payload = lesson.json()
    assert len(payload["segments"]) == 1
    assert payload["segments"][0]["recognized_english"] == "Today we will talk about baptism."
    assert "baptism" in payload["segments"][0]["delivered_spanish"]

    # Worker should draft an outline without blocking the end response.
    for _ in range(40):
        refreshed = client.get(f"/api/v1/lessons/{body['lesson_id']}", headers=lesson_headers).json()
        if refreshed["outline"]["status"] in {"draft", "failed"}:
            break
        time.sleep(0.1)
    assert refreshed["outline"]["status"] == "draft"
    assert "baptism" in refreshed["outline"]["english"].lower()

    saved = client.post(
        f"/api/v1/lessons/{body['lesson_id']}/outline",
        headers=lesson_headers,
        json={
            "english": refreshed["outline"]["english"],
            "spanish": refreshed["outline"]["spanish"],
            "ai_additions": refreshed["outline"]["ai_additions"],
            "approve": True,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["outline"]["status"] == "approved"

    quiz = client.post(
        f"/api/v1/lessons/{body['lesson_id']}/quiz",
        headers=lesson_headers,
        json={"generate": True, "count": 3},
    )
    assert quiz.status_code == 200
    assert quiz.json()["quiz"]["status"] == "draft"
    assert len(quiz.json()["quiz"]["items"]) == 3

    published = client.post(
        f"/api/v1/lessons/{body['lesson_id']}/publish",
        headers=lesson_headers,
        json={"include_transcript": False},
    )
    assert published.status_code == 200
    share_path = published.json()["publication"]["share_path"]
    assert share_path.startswith("/share/")
    share_token = share_path.rsplit("/", 1)[-1]
    shared = client.get(f"/api/v1/share/{share_token}")
    assert shared.status_code == 200
    assert "baptism" in shared.json()["outline"]["english"].lower()
    assert shared.json()["transcript"] is None

    revoked = client.post(f"/api/v1/lessons/{body['lesson_id']}/unpublish", headers=lesson_headers)
    assert revoked.status_code == 200
    missing = client.get(f"/api/v1/share/{share_token}")
    assert missing.status_code == 404


def test_course_memory_and_augmentation_modes(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first = client.post("/api/v1/classes").json()
    teacher = {"X-Class-Token": first["teacher_token"]}
    client.post(
        "/api/v1/classes/line",
        headers=teacher,
        json={"text": "Baptism washes away original sin."},
    )
    ended = client.post("/api/v1/classes/end", headers=teacher).json()
    headers = {"X-Lesson-Token": ended["lesson_token"]}
    client.patch(
        f"/api/v1/lessons/{ended['lesson_id']}/course",
        headers=headers,
        json={"course_id": "rcia-fall", "course_title": "RCIA Fall"},
    )
    for _ in range(40):
        refreshed = client.get(f"/api/v1/lessons/{ended['lesson_id']}", headers=headers).json()
        if refreshed["outline"]["status"] in {"draft", "failed"}:
            break
        time.sleep(0.1)
    client.post(
        f"/api/v1/lessons/{ended['lesson_id']}/outline",
        headers=headers,
        json={
            "english": refreshed["outline"]["english"] or "Baptism overview",
            "spanish": refreshed["outline"]["spanish"] or "Resumen del bautismo",
            "ai_additions": [],
            "approve": True,
        },
    )

    second = client.post("/api/v1/classes").json()
    teacher2 = {"X-Class-Token": second["teacher_token"]}
    ended2 = client.post("/api/v1/classes/end", headers=teacher2).json()
    headers2 = {"X-Lesson-Token": ended2["lesson_token"]}
    client.patch(
        f"/api/v1/lessons/{ended2['lesson_id']}/course",
        headers=headers2,
        json={"course_id": "rcia-fall", "course_title": "RCIA Fall"},
    )

    viewed = client.get(f"/api/v1/lessons/{ended2['lesson_id']}", headers=headers2).json()
    assert viewed["course_id"] == "rcia-fall"
    assert any(item["lesson_id"] == ended["lesson_id"] for item in viewed["course_memory"])
    assert any(item["lesson_id"] == ended["lesson_id"] for item in viewed["course_history"])

    for mode in ("off", "critical", "light"):
        regen = client.post(
            f"/api/v1/lessons/{ended2['lesson_id']}/outline",
            headers=headers2,
            json={"regenerate": True, "augmentation": mode},
        )
        assert regen.status_code == 200
        assert regen.json()["outline"]["augmentation"] == mode


def test_student_cannot_read_lesson(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    opened = client.post("/api/v1/classes").json()
    teacher = {"X-Class-Token": opened["teacher_token"]}
    client.post("/api/v1/classes/line", headers=teacher, json={"text": "Peace be with you."})
    ended = client.post("/api/v1/classes/end", headers=teacher).json()
    denied = client.get(
        f"/api/v1/lessons/{ended['lesson_id']}",
        headers={"X-Lesson-Token": "not-the-token"},
    )
    assert denied.status_code == 403


def test_correction_keeps_original_segment(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    opened = client.post("/api/v1/classes").json()
    teacher = {"X-Class-Token": opened["teacher_token"]}
    client.post("/api/v1/classes/line", headers=teacher, json={"text": "God is love."})
    ended = client.post("/api/v1/classes/end", headers=teacher).json()
    headers = {"X-Lesson-Token": ended["lesson_token"]}
    lesson = client.get(f"/api/v1/lessons/{ended['lesson_id']}", headers=headers).json()
    segment_id = lesson["segments"][0]["id"]
    original = lesson["segments"][0]["recognized_english"]
    corrected = client.post(
        f"/api/v1/lessons/{ended['lesson_id']}/corrections",
        headers=headers,
        json={
            "segment_id": segment_id,
            "language": "en",
            "corrected_text": "God is love.",
            "reason": "punctuation",
        },
    )
    assert corrected.status_code == 200
    body = corrected.json()
    assert body["segments"][0]["recognized_english"] == original
    assert body["corrections"][0]["corrected_text"] == "God is love."

    quality = client.post(
        f"/api/v1/lessons/{ended['lesson_id']}/quality",
        headers=headers,
        json={"segment_id": segment_id, "rating": 5, "note": "clear"},
    )
    assert quality.status_code == 200
    assert quality.json()["quality_notes"][0]["rating"] == 5

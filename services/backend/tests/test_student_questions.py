from __future__ import annotations

from fastapi.testclient import TestClient

from app.classroom import reset_classes
from app.main import create_app
from babelbeam_runtime import Settings
from babelbeam_runtime.config import PLAN_PATH


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    reset_classes()
    settings = Settings(
        plan_path=PLAN_PATH,
        provider_mode="mock",
        openai_api_key="",
        _env_file=None,  # type: ignore[call-arg]
    )
    return TestClient(create_app(settings))


def test_join_requires_a_display_name(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    opened = client.post("/api/v1/classes").json()
    missing = client.post("/api/v1/classes/join", json={"join_code": opened["join_code"]})
    assert missing.status_code == 400
    assert missing.json()["status"] == "name_required"


def test_live_question_uses_mateo_style_voice_for_boy(tmp_path, monkeypatch) -> None:
    calls: list[dict[str, str]] = []

    def fake_transcribe(*_args: object, **_kwargs: object) -> str:
        return "Hola"

    def fake_speech(
        _settings: object,
        text: str,
        language: str,
        *,
        provider_voice: str = "",
        instructions: str = "",
    ) -> tuple[str, str]:
        calls.append(
            {
                "text": text,
                "language": language,
                "provider_voice": provider_voice,
                "instructions": instructions,
            }
        )
        return "YQ==", "audio/mpeg"

    def fake_interpret(*_args: object, include_audio: bool = False, **_kwargs: object) -> dict[str, object]:
        return {
            "translated_text": "Hello.",
            "audio_base64": "",
            "audio_content_type": "",
            "simulated": False,
        }

    def refuse_cleanup(*_args: object, **_kwargs: object) -> object:
        from app.phrase_cleanup import CleanupRejected

        raise CleanupRejected("unit")

    monkeypatch.setattr("app.classroom.transcribe_audio", fake_transcribe)
    monkeypatch.setattr("app.classroom.synthesize_speech", fake_speech)
    monkeypatch.setattr("app.classroom.interpret_text", fake_interpret)
    monkeypatch.setattr("app.phrase_cleanup._call", refuse_cleanup)
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board-gender.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    from app.classroom import reset_classes
    from app.main import create_app
    from babelbeam_runtime import Settings
    from babelbeam_runtime.config import PLAN_PATH

    reset_classes()
    settings = Settings(
        plan_path=PLAN_PATH,
        provider_mode="live",
        openai_api_key="test-key",
        openai_tts_model="gpt-4o-mini-tts",
        _env_file=None,  # type: ignore[call-arg]
    )
    client = TestClient(create_app(settings))
    opened = client.post("/api/v1/classes").json()
    boy = client.post(
        "/api/v1/classes/join",
        json={"join_code": opened["join_code"], "display_name": "Luis", "gender": "boy"},
    ).json()
    reply = client.post(
        "/api/v1/classes/student-utterance",
        headers={"X-Class-Token": boy["student_token"]},
        files={"audio": ("speech.webm", b"x" * 500, "audio/webm")},
    )
    assert reply.status_code == 200, reply.text
    assert calls
    assert calls[0]["provider_voice"] == "verse"
    assert "young man" in calls[0]["instructions"]
    assert "child" not in calls[0]["instructions"].lower()


def test_two_students_can_leave_named_questions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.classroom.transcribe_audio",
        lambda *_args, **_kwargs: "Gracias",
    )
    client = _client(tmp_path, monkeypatch)
    opened = client.post("/api/v1/classes").json()
    teacher = {"X-Class-Token": opened["teacher_token"]}
    ana = client.post(
        "/api/v1/classes/join",
        json={"join_code": opened["join_code"], "display_name": "Ana", "gender": "girl"},
    ).json()
    luis = client.post(
        "/api/v1/classes/join",
        json={"join_code": opened["join_code"], "display_name": "Luis", "gender": "boy"},
    ).json()
    assert ana["gender"] == "girl"
    assert luis["gender"] == "boy"
    clip = b"x" * 500
    first = client.post(
        "/api/v1/classes/student-utterance",
        headers={"X-Class-Token": ana["student_token"]},
        files={"audio": ("speech.webm", clip, "audio/webm")},
    )
    second = client.post(
        "/api/v1/classes/student-utterance",
        headers={"X-Class-Token": luis["student_token"]},
        files={"audio": ("speech.webm", clip, "audio/webm")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    cues = client.get("/api/v1/classes/cues", headers=teacher)
    body = cues.json()
    assert cues.status_code == 200
    assert body["unread_count"] == 2
    names = {item["student_name"] for item in body["cues"]}
    assert names == {"Ana", "Luis"}
    genders = {item["speaker_gender"] for item in body["cues"]}
    assert genders == {"boy", "girl"}
    assert all(item["listened"] is False for item in body["cues"])
    assert "audio_base64" not in body["cues"][0]
    one = client.get(f"/api/v1/classes/questions/{body['cues'][0]['id']}", headers=teacher)
    assert one.status_code == 200
    assert one.json()["cue"]["student_name"] in {"Ana", "Luis"}
    assert one.json()["cue"]["speaker_gender"] in {"boy", "girl"}
    heard = client.post(
        "/api/v1/classes/questions/heard",
        headers=teacher,
        json={"cue_id": body["cues"][0]["id"]},
    )
    assert heard.status_code == 200
    assert heard.json()["unread_count"] == 1
    again = client.get("/api/v1/classes/cues", headers=teacher).json()
    assert again["unread_count"] == 1
    assert sum(1 for item in again["cues"] if item["listened"]) == 1
    feed = client.get(
        "/api/v1/classes/feed",
        headers={"X-Class-Token": ana["student_token"]},
    )
    assert "Gracias" not in feed.text
    deferred = client.post(
        "/api/v1/classes/questions/handling",
        headers=teacher,
        json={"cue_id": body["cues"][1]["id"], "handling": "deferred"},
    )
    assert deferred.status_code == 200
    assert deferred.json()["handling"] == "deferred"
    assert deferred.json()["unread_count"] == 0
    after_defer = client.get("/api/v1/classes/cues", headers=teacher).json()
    assert after_defer["unread_count"] == 0
    deferred_cue = next(item for item in after_defer["cues"] if item["id"] == body["cues"][1]["id"])
    assert deferred_cue["handling"] == "deferred"
    assert deferred_cue["listened"] is True

    ended = client.post("/api/v1/classes/end", headers=teacher)
    assert ended.status_code == 200
    gone = client.get("/api/v1/classes/cues", headers=teacher)
    assert gone.status_code in {200, 404}
    if gone.status_code == 200:
        assert gone.json()["cues"] == []

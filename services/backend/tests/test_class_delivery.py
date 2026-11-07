"""Ordered, lossless class delivery: board merging, caption before audio, timing safety."""

from __future__ import annotations

import base64
import copy
import json
import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import board_merge, classroom, interpret
from app.classroom import LineOrder, parse_line_order, reset_classes
from app.main import create_app
from babelbeam_runtime import Settings
from babelbeam_runtime.config import PLAN_PATH

LIVE_KEY = "sk-test-not-a-real-key-for-unit-tests-only"


def _settings(mode: str = "mock") -> Settings:
    return Settings(
        plan_path=PLAN_PATH,
        provider_mode=mode,
        openai_api_key=LIVE_KEY if mode == "live" else "",
        openai_tts_model="gpt-4o-mini-tts",
        _env_file=None,  # type: ignore[call-arg]
    )


def _segment(seg_id: str, appended: int, state: str = "ready") -> dict[str, Any]:
    return {
        "id": seg_id,
        "spanish_text": f"linea {seg_id}",
        "audio_base64": "" if state == "pending" else "QUJD",
        "audio_content_type": "" if state == "pending" else "audio/mpeg",
        "simulated": False,
        "audio_state": state,
        "appended_ns": appended,
        "ready_ns": appended,
        "seq": None,
        "wait_for": [],
    }


def _room(segments: list[dict[str, Any]], tokens: list[str]) -> dict[str, Any]:
    return {
        "id": "room-1",
        "code": "123456",
        "teacher_token": "teacher",
        "student_tokens": tokens,
        "status": "live",
        "segments": segments,
        "cues": [],
        "student_turn_until": None,
        "created_at": time.time(),
        "ended_at": None,
    }


def test_merge_keeps_both_concurrent_appends_in_append_order() -> None:
    base = _room([_segment("a", 10)], ["s1"])
    left = copy.deepcopy(base)
    left["segments"].append(_segment("c", 30))
    right = copy.deepcopy(base)
    right["segments"].append(_segment("b", 20))
    right["student_tokens"].append("s2")
    merged = board_merge.merge_snapshots([{"rooms": [left]}, {"rooms": [right]}])
    room = merged["rooms"][0]
    assert [item["id"] for item in room["segments"]] == ["a", "b", "c"]
    assert room["student_tokens"] == ["s1", "s2"]


def test_merge_keeps_ended_final_and_finished_audio() -> None:
    live = _room([_segment("a", 10, "pending")], ["s1"])
    finished = copy.deepcopy(live)
    finished["segments"][0] = _segment("a", 10, "ready")
    merged = board_merge.merge_snapshots([{"rooms": [finished]}, {"rooms": [live]}])
    assert merged["rooms"][0]["segments"][0]["audio_state"] == "ready"
    ended = copy.deepcopy(live)
    ended["status"] = "ended"
    ended["ended_at"] = time.time()
    ended["segments"] = []
    again = board_merge.merge_snapshots([{"rooms": [ended]}, {"rooms": [finished]}])
    assert again["rooms"][0]["status"] == "ended"
    assert again["rooms"][0]["segments"] == []


class FakeBlobStore:
    """In-memory stand-in for the Vercel Blob list, get, put, and delete calls."""

    def __init__(self) -> None:
        self.items: dict[str, tuple[int, dict[str, Any]]] = {}
        self.clock = 0
        self.lock = threading.Lock()

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "fake-blob-token")
        monkeypatch.setattr(classroom, "_list_boards", self.list_boards)
        monkeypatch.setattr(classroom, "_get_board", self.get_board)
        monkeypatch.setattr(classroom, "_delete_pathname", self.delete)
        monkeypatch.setattr(classroom.httpx, "put", self.put)

    def list_boards(self, _token: str) -> list[dict[str, Any]]:
        with self.lock:
            return [
                {
                    "pathname": name,
                    "uploadedAt": f"2026-10-24T00:00:{stamp:06d}Z",
                    "downloadUrl": name,
                }
                for name, (stamp, _payload) in sorted(self.items.items())
            ]

    def get_board(self, _token: str, item: dict[str, Any]) -> dict[str, Any] | None:
        with self.lock:
            found = self.items.get(str(item["pathname"]))
        return copy.deepcopy(found[1]) if found else None

    def delete(self, _token: str, pathname: str) -> None:
        with self.lock:
            self.items.pop(pathname, None)

    def put(self, _url: str, **kwargs: Any) -> Any:
        pathname = str(kwargs["params"]["pathname"])
        payload = json.loads(kwargs["content"])
        with self.lock:
            self.clock += 1
            self.items[pathname] = (self.clock, payload)

        class Response:
            status_code = 200

        return Response()


@contextmanager
def _instance(state: dict[str, Any]) -> Iterator[None]:
    """Run classroom calls as if inside a separate serverless instance."""
    saved = (
        copy.deepcopy(classroom._BOARD),
        classroom._LOADED,
        classroom._LOADED_AT,
        list(classroom._MERGED_PATHNAMES),
    )
    classroom._BOARD.clear()
    classroom._BOARD.update(state.get("board", {"rooms": [], "revision": 0}))
    classroom._LOADED = bool(state.get("loaded", False))
    classroom._LOADED_AT = 0.0
    classroom._MERGED_PATHNAMES[:] = state.get("merged", [])
    try:
        yield
    finally:
        state["board"] = copy.deepcopy(classroom._BOARD)
        state["loaded"] = classroom._LOADED
        state["merged"] = list(classroom._MERGED_PATHNAMES)
        classroom._BOARD.clear()
        classroom._BOARD.update(saved[0])
        classroom._LOADED = saved[1]
        classroom._LOADED_AT = saved[2]
        classroom._MERGED_PATHNAMES[:] = saved[3]


def test_interleaved_writers_on_two_instances_lose_nothing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    store = FakeBlobStore()
    store.install(monkeypatch)
    first: dict[str, Any] = {}
    second: dict[str, Any] = {}
    with _instance(first):
        opened = classroom.start_class()
        token = opened["teacher_token"]
    # Both instances load the same snapshot, then each appends a different line.
    with _instance(first), classroom._LOCK:
        classroom._load_unlocked()
        room = classroom._room_by_token_unlocked(token)
        assert room is not None
        room["segments"].append(_segment("from-first", time.time_ns()))
    with _instance(second):
        classroom._append_segment(token, _segment("from-second", time.time_ns()))
        joined = classroom.join_class(opened["join_code"], display_name="Ana")
    with _instance(first), classroom._LOCK:
        classroom._persist_unlocked()
    reader: dict[str, Any] = {}
    with _instance(reader):
        heard = classroom.feed(joined["student_token"], "", version=2, first=True)
    ids = [item["id"] for item in heard["segments"]]
    assert sorted(ids) == ["from-first", "from-second"]
    assert len(store.items) <= 3


def test_late_and_out_of_order_lines_keep_teacher_order(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    reset_classes()
    client = TestClient(create_app(_settings()))
    opened = client.post("/api/v1/classes").json()
    teacher = {"X-Class-Token": opened["teacher_token"]}
    student = {"X-Class-Token": client.post(
        "/api/v1/classes/join", json={"join_code": opened["join_code"], "display_name": "Ana"}
    ).json()["student_token"]}
    history = client.get("/api/v1/classes/feed?v=2&first=1", headers=student)
    assert history.json()["segments"] == []
    later = client.post(
        "/api/v1/classes/line",
        headers={**teacher, "X-Line-Seq": "2", "X-Line-Wait": "1"},
        json={"text": "Second."},
    )
    earlier = client.post(
        "/api/v1/classes/line",
        headers={**teacher, "X-Line-Seq": "1"},
        json={"text": "First."},
    )
    assert later.status_code == 200
    assert earlier.status_code == 200
    assert later.json()["seq"] == 2
    heard = client.get("/api/v1/classes/feed?v=2", headers=student).json()["segments"]
    by_seq = sorted(heard, key=lambda item: item["seq"])
    assert [item["spanish_text"] for item in by_seq] == ["[mock:es] First.", "[mock:es] Second."]
    assert by_seq[1]["wait_for"] == [1]
    known = ",".join(item["id"] for item in heard)
    again = client.get(f"/api/v1/classes/feed?v=2&have={known}", headers=student)
    assert again.json()["segments"] == []
    legacy = client.get("/api/v1/classes/feed", headers=student).json()["segments"]
    assert [item["spanish_text"] for item in legacy] == ["[mock:es] Second.", "[mock:es] First."]
    assert set(legacy[0]) == {
        "id",
        "spanish_text",
        "audio_base64",
        "audio_content_type",
        "simulated",
    }


def test_caption_reaches_students_before_audio(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    reset_classes()
    release = threading.Event()
    calls: list[str] = []

    def fake_interpret(*_args: object, include_audio: bool = False) -> dict[str, object]:
        assert include_audio is False
        return {"translated_text": "La paz sea contigo.", "simulated": False}

    def fake_speech(
        _settings: object,
        text: str,
        language: str,
        **_kwargs: object,
    ) -> tuple[str, str]:
        calls.append(language)
        assert release.wait(5.0)
        return base64.b64encode(b"mpeg-frames").decode("ascii"), "audio/mpeg"

    def refuse_cleanup(*_args: object, **_kwargs: object) -> object:
        from app.phrase_cleanup import CleanupRejected

        raise CleanupRejected("unit")

    monkeypatch.setattr(classroom, "interpret_text", fake_interpret)
    monkeypatch.setattr(classroom, "synthesize_line", fake_speech)
    monkeypatch.setattr("app.phrase_cleanup._call", refuse_cleanup)
    settings = _settings("live")
    opened = classroom.start_class()
    student = classroom.join_class(opened["join_code"], display_name="Ana")["student_token"]
    results: list[dict[str, object]] = []
    worker = threading.Thread(
        target=lambda: results.append(
            classroom.post_line(opened["teacher_token"], settings, "Peace.", LineOrder(seq=1))
        )
    )
    worker.start()
    deadline = time.monotonic() + 5.0
    pending: Any = []
    while time.monotonic() < deadline and not pending:
        pending = classroom.feed(student, "", version=2)["segments"]
        time.sleep(0.01)
    assert pending, "the caption was not published before the audio finished"
    assert pending[0]["audio_state"] == "pending"
    assert "audio_base64" not in pending[0]
    assert classroom.feed(student, "")["segments"] == []
    release.set()
    worker.join(5.0)
    assert results and results[0]["audio_available"] is True
    done: Any = classroom.feed(student, "", version=2)["segments"]
    assert done[0]["audio_state"] == "ready"
    assert done[0]["audio_base64"] == base64.b64encode(b"mpeg-frames").decode("ascii")
    assert calls == ["es"]
    legacy: Any = classroom.feed(student, "")["segments"]
    assert len(legacy) == 1


def test_teacher_only_cues_never_reach_the_v2_feed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setattr("app.classroom.transcribe_audio", lambda *_args, **_kwargs: "Gracias")
    reset_classes()
    client = TestClient(create_app(_settings()))
    opened = client.post("/api/v1/classes").json()
    student = {"X-Class-Token": client.post(
        "/api/v1/classes/join", json={"join_code": opened["join_code"], "display_name": "Ana"}
    ).json()["student_token"]}
    reply = client.post(
        "/api/v1/classes/student-utterance",
        headers=student,
        files={"audio": ("speech.webm", b"x" * 500, "audio/webm")},
    )
    assert reply.status_code == 200
    for query in ("?v=2&first=1", "?v=2", ""):
        heard = client.get(f"/api/v1/classes/feed{query}", headers=student)
        assert heard.status_code == 200
        assert heard.json()["segments"] == []
        assert "Gracias" not in heard.text


def test_spanish_heard_on_the_teacher_microphone_is_not_published_again(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)

    def spanish_echo(
        *_args: object, languages_out: list[str] | None = None, **_kwargs: object
    ) -> str:
        if languages_out is not None:
            languages_out.append("es")
        return "La paz sea contigo."

    monkeypatch.setattr("app.classroom.transcribe_audio", spanish_echo)
    reset_classes()
    client = TestClient(create_app(_settings()))
    opened = client.post("/api/v1/classes").json()
    teacher = {"X-Class-Token": opened["teacher_token"], "X-Line-Seq": "1"}
    student = {"X-Class-Token": client.post(
        "/api/v1/classes/join", json={"join_code": opened["join_code"], "display_name": "Ana"}
    ).json()["student_token"]}
    spoken = client.post(
        "/api/v1/classes/utterance",
        headers=teacher,
        files={"audio": ("speech.wav", b"x" * 500, "audio/wav")},
    )
    assert spoken.status_code == 200
    assert spoken.json()["status"] == "skipped"
    assert client.get("/api/v1/classes/feed?v=2", headers=student).json()["segments"] == []
    assert classroom.heard_only_spanish(["en", "es"]) is False
    assert classroom.heard_only_spanish([]) is False


def test_line_order_headers_are_bounded() -> None:
    assert parse_line_order("3", "1,2,9,2,x") == LineOrder(seq=3, wait_for=(1, 2))
    assert parse_line_order("", "") is None
    assert parse_line_order("0", "") is None
    assert parse_line_order("99999999", "") is None
    many = ",".join(str(value) for value in range(1, 40))
    parsed = parse_line_order("50", many)
    assert parsed is not None and len(parsed.wait_for) == 8


def test_speech_parts_are_split_in_order_and_joined_once(monkeypatch) -> None:
    parts = interpret.split_for_speech(
        "La paz sea con ustedes. Hoy hablaremos de los sacramentos. ¿Listos? Bien."
    )
    assert parts == [
        "La paz sea con ustedes.",
        "Hoy hablaremos de los sacramentos. ¿Listos? Bien.",
    ]
    assert interpret.split_for_speech("Sí.") == ["Sí."]
    long_text = " ".join(f"Frase numero {index} con varias palabras." for index in range(9))
    assert len(interpret.split_for_speech(long_text)) == 4
    calls: list[str] = []

    def fake_synthesize(
        _settings: object, text: str, _target: str, **_kwargs: object
    ) -> tuple[str, str]:
        calls.append(text)
        return base64.b64encode(text.encode("utf-8")).decode("ascii"), "audio/mpeg"

    monkeypatch.setattr(interpret, "_synthesize", fake_synthesize)
    joined = interpret.synthesize_line(
        _settings("live"), "La paz sea con ustedes. Hoy hablaremos de los sacramentos.", "es"
    )
    assert joined is not None
    assert base64.b64decode(joined[0]) == (
        b"La paz sea con ustedes.Hoy hablaremos de los sacramentos."
    )
    assert sorted(calls) == sorted(
        ["La paz sea con ustedes.", "Hoy hablaremos de los sacramentos."]
    )

    def failing_part(
        _settings: object, text: str, _target: str, **_kwargs: object
    ) -> tuple[str, str] | None:
        return None if text.startswith("Hoy") else ("QQ==", "audio/mpeg")

    monkeypatch.setattr(interpret, "_synthesize", failing_part)
    assert interpret.synthesize_line(
        _settings("live"), "La paz sea con ustedes. Hoy hablaremos de los sacramentos.", "es"
    ) is None
    assert interpret.synthesize_line(_settings("mock"), "Hola.", "es") is None


def test_timing_header_and_log_hold_stage_names_and_numbers_only(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setattr(
        "app.classroom.transcribe_audio", lambda *_args, **_kwargs: "Peace be with you."
    )
    reset_classes()
    client = TestClient(create_app(_settings()))
    opened = client.post("/api/v1/classes").json()
    spoken = client.post(
        "/api/v1/classes/utterance",
        headers={"X-Class-Token": opened["teacher_token"], "X-Line-Seq": "1"},
        files={"audio": ("speech.wav", b"x" * 500, "audio/wav")},
    )
    assert spoken.status_code == 200
    header = spoken.headers["server-timing"]
    for entry in header.split(", "):
        assert re.fullmatch(r"[a-z][a-z0-9_]*;dur=\d+", entry), entry
    assert "auth;dur=" in header and "total;dur=" in header
    logged = capsys.readouterr().out
    lines = [line for line in logged.splitlines() if line.startswith("bb_timing")]
    assert lines
    for line in lines:
        assert re.fullmatch(r"bb_timing( [a-z][a-z0-9_]*=\d+| route=[a-z_]+)+", line), line
        assert "Peace" not in line and opened["teacher_token"] not in line
        assert opened["join_code"] not in line


def test_class_line_synthesizes_once_per_distinct_voice(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    reset_classes()
    voices: list[str] = []

    def fake_interpret(*_args: object, include_audio: bool = False) -> dict[str, object]:
        assert include_audio is False
        return {"translated_text": "La paz sea contigo.", "simulated": False}

    def fake_speech(
        _settings: object,
        _text: str,
        language: str,
        *,
        provider_voice: str = "",
        instructions: str = "",
    ) -> tuple[str, str]:
        voices.append(provider_voice)
        clip = base64.b64encode(provider_voice.encode("ascii")).decode("ascii")
        return clip, "audio/mpeg"

    def refuse_cleanup(*_args: object, **_kwargs: object) -> object:
        from app.phrase_cleanup import CleanupRejected

        raise CleanupRejected("unit")

    monkeypatch.setattr(classroom, "interpret_text", fake_interpret)
    monkeypatch.setattr(classroom, "synthesize_line", fake_speech)
    monkeypatch.setattr("app.phrase_cleanup._call", refuse_cleanup)
    settings = _settings("live")
    opened = classroom.start_class()
    first = classroom.join_class(opened["join_code"], "felipe", display_name="Ana")["student_token"]
    second = classroom.join_class(opened["join_code"], "felipe", display_name="Ana")["student_token"]
    third = classroom.join_class(opened["join_code"], "mateo", display_name="Ana")["student_token"]
    classroom.post_line(opened["teacher_token"], settings, "Peace be with you.")
    # Distinct student voices plus the default voice kept as a silent-fallback clip.
    assert sorted(voices) == ["cedar", "marin", "verse"]
    felipe = classroom.feed(first, "", version=2)["segments"][0]
    mateo = classroom.feed(third, "", version=2)["segments"][0]
    again = classroom.feed(second, "", version=2)["segments"][0]
    assert felipe["audio_base64"] == again["audio_base64"]
    assert felipe["audio_base64"] != mateo["audio_base64"]
    assert base64.b64decode(felipe["audio_base64"]) == b"cedar"
    assert base64.b64decode(mateo["audio_base64"]) == b"verse"


def test_feed_falls_back_when_chosen_voice_clip_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BABELBEAM_CLASS_FILE", str(tmp_path / "board.json"))
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    reset_classes()

    def fake_interpret(*_args: object, include_audio: bool = False) -> dict[str, object]:
        return {"translated_text": "La paz sea contigo.", "simulated": False}

    def fake_speech(
        _settings: object,
        _text: str,
        language: str,
        *,
        provider_voice: str = "",
        instructions: str = "",
    ) -> tuple[str, str]:
        clip = base64.b64encode(provider_voice.encode("ascii")).decode("ascii")
        return clip, "audio/mpeg"

    def refuse_cleanup(*_args: object, **_kwargs: object) -> object:
        from app.phrase_cleanup import CleanupRejected

        raise CleanupRejected("unit")

    monkeypatch.setattr(classroom, "interpret_text", fake_interpret)
    monkeypatch.setattr(classroom, "synthesize_line", fake_speech)
    monkeypatch.setattr("app.phrase_cleanup._call", refuse_cleanup)
    settings = _settings("live")
    opened = classroom.start_class()
    # Teacher speaks before any student joins, so only the default voice is stored.
    classroom.post_line(opened["teacher_token"], settings, "Peace be with you.")
    late = classroom.join_class(opened["join_code"], "felipe", display_name="Ana")["student_token"]
    history = classroom.feed(late, "", version=2, first=True)["segments"]
    assert history[0]["spanish_text"] == "La paz sea contigo."
    assert "audio_base64" not in history[0]
    # A later line that somehow only has Valeria still reaches Felipe via fallback.
    room = classroom._BOARD["rooms"][0]
    segment = {
        "id": "fallback-clip",
        "spanish_text": "Seguimos.",
        "audio_base64": "",
        "audio_content_type": "",
        "simulated": False,
        "audio_state": "ready",
        "appended_ns": 1,
        "ready_ns": 2,
        "seq": 2,
        "wait_for": [],
        "clips": {
            "valeria": {
                "audio_base64": base64.b64encode(b"marin").decode("ascii"),
                "audio_content_type": "audio/mpeg",
            }
        },
    }
    room["segments"].append(segment)
    heard = classroom.feed(late, "", version=2, have=history[0]["id"])["segments"]
    assert heard[0]["id"] == "fallback-clip"
    assert heard[0]["audio_base64"]
    assert base64.b64decode(heard[0]["audio_base64"]) == b"marin"

"""Public health and configuration routes. No classroom or billing actions yet."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import timing
from app import lesson_gen, lessons
from app.classroom import (
    LineOrder,
    end_class,
    feed,
    join_class,
    get_question,
    mark_question_heard,
    set_question_handling,
    parse_line_order,
    post_line,
    post_student_audio,
    post_teacher_audio,
    rehearsal_step,
    say_next_lines,
    set_student_voice,
    start_class,
    teacher_cues,
)
from app.errors import ClassError
from app.interpret import interpret_text
from app.phrase_cleanup import ContextLineIn, parse_context_field, parse_mode
from babelbeam_runtime import Settings, simulated
from babelbeam_runtime.config import load_plan


class InterpretIn(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    source_language: str = "en"
    target_language: str = "es"
    include_audio: bool = False


class JoinIn(BaseModel):
    join_code: str = Field(min_length=4, max_length=12)
    voice: str = ""
    display_name: str = Field(default="", max_length=80)
    gender: str = Field(default="", max_length=20)


class HeardIn(BaseModel):
    cue_id: str = Field(min_length=4, max_length=64)


class QuestionHandlingIn(BaseModel):
    cue_id: str = Field(min_length=4, max_length=64)
    handling: Literal["heard", "deferred", "dismissed", "open"] = "heard"


class LineIn(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    context: list[ContextLineIn] = Field(default_factory=list)
    mode: Literal["clean", "verbatim"] = "clean"


class SayNextIn(BaseModel):
    context: list[ContextLineIn] = Field(default_factory=list)


class VoiceIn(BaseModel):
    voice: str = Field(min_length=1, max_length=20)


class RehearseIn(BaseModel):
    step: Literal["intro", "explain", "reply"]
    spanish_text: str = Field(default="", max_length=400)

router = APIRouter()


@router.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "babelbeam-api"}


@router.get("/api/v1/ready")
def ready(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    checks: dict[str, str] = {"config": "ok"}
    if settings.database_url:
        checks["database"] = "configured_not_probed_in_phase0"
    else:
        checks["database"] = "skipped"
    if settings.redis_url:
        checks["redis"] = "configured_not_probed_in_phase0"
    else:
        checks["redis"] = "skipped"
    # Phase 0 does not claim dependency probes passed. Unset local deps are skipped.
    # A configured URL is reported as not probed so operators do not treat this as proof.
    is_ready = checks["database"] != "down" and checks["redis"] != "down"
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={"ready": is_ready, "checks": checks},
    )


@router.get("/api/v1/public/config")
def public_config(request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    plan = load_plan(settings.plan_path)
    return {
        "app_name": "BabelBeam",
        "provider_mode": settings.provider_mode,
        "simulated": simulated(settings),
        "price_cents": plan["amount_cents"],
        "trial_days": plan["trial_days"],
        "currency": plan["currency"],
        "student_price_cents": plan["student_price_cents"],
        "max_student_listeners": plan["max_student_listeners"],
        "included_class_seconds": plan["included_class_seconds_per_paid_period"],
        "plan_limits_approved": settings.plan_limits_approved,
        "limits_are_proposed": plan["proposed_limits_require_owner_approval"],
        "minors_enabled": settings.minors_enabled,
        "production_billing_enabled": settings.production_billing_enabled,
        "billing_implemented": False,
    }


@router.post("/api/v1/interpret")
def interpret(body: InterpretIn, request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    try:
        result = interpret_text(
            settings,
            body.text,
            body.source_language,
            body.target_language,
            include_audio=body.include_audio,
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"status": "rejected", "detail": str(exc)})
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "detail": str(exc),
                "simulated": False,
                "audio_available": False,
            },
        )
    return JSONResponse(status_code=200, content=result)


def _class_token(request: Request) -> str:
    return request.headers.get("x-class-token", "").strip()


def _class_error(exc: ClassError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"status": exc.code})


def _form_context(raw: str) -> list[object]:
    try:
        return list(parse_context_field(raw))
    except ValueError:
        return []


def _form_mode(raw: str) -> str:
    try:
        return parse_mode(raw)
    except ValueError:
        return "clean"


def _line_order(request: Request) -> LineOrder | None:
    return parse_line_order(
        request.headers.get("x-line-seq", ""),
        request.headers.get("x-line-wait", ""),
    )


def _timed_json(route: str, call: Callable[[], dict[str, object]]) -> JSONResponse:
    """Run one class call. The Server-Timing header and log hold stage names and ms only."""
    with timing.request_timer(route) as timer:
        try:
            response = JSONResponse(status_code=200, content=call())
        except ClassError as exc:
            response = _class_error(exc)
        except ValueError:
            response = JSONResponse(status_code=400, content={"status": "rejected"})
        except RuntimeError:
            response = JSONResponse(status_code=503, content={"status": "unavailable"})
    response.headers["Server-Timing"] = timer.server_timing()
    timing.emit(timer, response.status_code)
    return response


@router.post("/api/v1/classes")
def open_class() -> dict[str, str]:
    return start_class()


@router.post("/api/v1/classes/join")
def join_open_class(body: JoinIn) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=join_class(body.join_code, body.voice, body.display_name, body.gender),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/classes/line")
def class_line(body: LineIn, request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    token = _class_token(request)
    order = _line_order(request)
    return _timed_json(
        "line",
        lambda: post_line(token, settings, body.text, order, body.context, body.mode),
    )


@router.post("/api/v1/classes/say-next")
def class_say_next(body: SayNextIn, request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    token = _class_token(request)
    return _timed_json("say_next", lambda: say_next_lines(token, settings, body.context))


@router.get("/api/v1/classes/feed")
def class_feed(
    request: Request,
    after: str = "",
    v: int = 1,
    have: str = "",
    first: int = 0,
) -> JSONResponse:
    token = _class_token(request)
    return _timed_json(
        "feed",
        lambda: feed(token, after, version=v, have=have[:2000], first=first == 1),
    )


@router.post("/api/v1/classes/utterance")
async def class_utterance(
    request: Request,
    audio: UploadFile = File(),
    context: str = Form(""),
    mode: str = Form("clean"),
) -> JSONResponse:
    order = _line_order(request)
    lines = _form_context(context)
    cleanup = _form_mode(mode)

    def teacher_turn(
        token: str, settings: Settings, payload: bytes, content_type: str
    ) -> dict[str, object]:
        return post_teacher_audio(
            token, settings, payload, content_type, order, lines, cleanup
        )

    return await _audio_turn(request, audio, teacher_turn, "utterance")


@router.post("/api/v1/classes/student-utterance")
async def student_utterance(
    request: Request,
    audio: UploadFile = File(),
    context: str = Form(""),
    mode: str = Form("clean"),
) -> JSONResponse:
    lines = _form_context(context)
    cleanup = _form_mode(mode)

    def student_turn(
        token: str, settings: Settings, payload: bytes, content_type: str
    ) -> dict[str, object]:
        return post_student_audio(token, settings, payload, content_type, lines, cleanup)

    return await _audio_turn(request, audio, student_turn, "student_utterance")


@router.post("/api/v1/classes/voice")
def class_voice(body: VoiceIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=set_student_voice(_class_token(request), body.voice),
        )
    except ClassError as exc:
        return _class_error(exc)
    except ValueError:
        return JSONResponse(status_code=400, content={"status": "rejected"})


@router.get("/api/v1/classes/cues")
def class_cues(request: Request, after: str = "") -> JSONResponse:
    try:
        return JSONResponse(status_code=200, content=teacher_cues(_class_token(request), after))
    except ClassError as exc:
        return _class_error(exc)


@router.get("/api/v1/classes/questions/{cue_id}")
def class_question(cue_id: str, request: Request) -> JSONResponse:
    try:
        return JSONResponse(status_code=200, content=get_question(_class_token(request), cue_id))
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/classes/questions/heard")
def class_question_heard(body: HeardIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=mark_question_heard(_class_token(request), body.cue_id),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/classes/questions/handling")
def class_question_handling(body: QuestionHandlingIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=set_question_handling(_class_token(request), body.cue_id, body.handling),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/classes/rehearse")
def class_rehearse(body: RehearseIn, request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    try:
        result = rehearsal_step(_class_token(request), settings, body.step, body.spanish_text)
    except ClassError as exc:
        return _class_error(exc)
    except ValueError:
        return JSONResponse(status_code=400, content={"status": "rejected"})
    except RuntimeError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content=result)


async def _audio_turn(
    request: Request,
    audio: UploadFile,
    handler: Callable[[str, Settings, bytes, str], dict[str, object]],
    route: str = "audio",
) -> JSONResponse:
    settings: Settings = request.app.state.settings
    payload = await audio.read(2_000_001)
    content_type = audio.content_type or ""
    token = _class_token(request)

    def call() -> dict[str, object]:
        timing.record_size("audio_in", len(payload))
        return handler(token, settings, payload, content_type)

    # Provider calls block for seconds. Running them off the event loop keeps feed polls
    # on the same instance from queueing behind an upload.
    return await run_in_threadpool(_timed_json, route, call)


@router.post("/api/v1/classes/end")
def close_class(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    try:
        result = end_class(_class_token(request))
        lesson_id = result.get("lesson_id") or ""
        if lesson_id:
            lesson_gen.request_outline(lesson_id, settings)
        return JSONResponse(status_code=200, content=result)
    except ClassError as exc:
        return _class_error(exc)


def _lesson_token(request: Request) -> str:
    return request.headers.get("x-lesson-token", "").strip()


class CourseIn(BaseModel):
    course_id: str = Field(default="", max_length=64)
    course_title: str = Field(default="", max_length=120)


class CorrectionIn(BaseModel):
    segment_id: str = Field(min_length=4, max_length=64)
    language: Literal["en", "es"]
    corrected_text: str = Field(min_length=1, max_length=800)
    reason: str = Field(default="", max_length=200)


class QualityIn(BaseModel):
    segment_id: str = Field(min_length=4, max_length=64)
    rating: int = Field(ge=1, le=5)
    note: str = Field(default="", max_length=400)


class OutlineIn(BaseModel):
    english: str = Field(default="", max_length=20000)
    spanish: str = Field(default="", max_length=20000)
    ai_additions: list[dict[str, object]] = Field(default_factory=list)
    approve: bool = False
    augmentation: Literal["off", "critical", "light"] = "critical"
    regenerate: bool = False


class QuizIn(BaseModel):
    count: int = Field(default=5, ge=3, le=10)
    formats: list[str] = Field(default_factory=lambda: ["multiple_choice", "reflection"])
    english: str = Field(default="", max_length=20000)
    spanish: str = Field(default="", max_length=20000)
    items: list[dict[str, object]] = Field(default_factory=list)
    approve: bool = False
    generate: bool = False


class PublishIn(BaseModel):
    include_transcript: bool = False
    expires_hours: int | None = Field(default=None, ge=1, le=24 * 90)


@router.get("/api/v1/lessons/{lesson_id}")
def lesson_get(lesson_id: str, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=lessons.get_lesson(_lesson_token(request), lesson_id),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.get("/api/v1/lessons")
def lesson_list(request: Request) -> JSONResponse:
    token = _lesson_token(request)
    if not token:
        return JSONResponse(status_code=401, content={"status": "unauthorized"})
    return JSONResponse(status_code=200, content={"lessons": lessons.list_recent_for_token(token)})


@router.patch("/api/v1/lessons/{lesson_id}/course")
def lesson_course(lesson_id: str, body: CourseIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=lessons.update_course(
                _lesson_token(request),
                lesson_id,
                body.course_id,
                body.course_title,
            ),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/lessons/{lesson_id}/corrections")
def lesson_correction(lesson_id: str, body: CorrectionIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=lessons.add_correction(
                _lesson_token(request),
                lesson_id,
                segment_id=body.segment_id,
                language=body.language,
                corrected_text=body.corrected_text,
                reason=body.reason,
            ),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/lessons/{lesson_id}/quality")
def lesson_quality(lesson_id: str, body: QualityIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=lessons.add_quality_note(
                _lesson_token(request),
                lesson_id,
                segment_id=body.segment_id,
                rating=body.rating,
                note=body.note,
            ),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/lessons/{lesson_id}/outline")
def lesson_outline(lesson_id: str, body: OutlineIn, request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    token = _lesson_token(request)
    try:
        if body.regenerate:
            lessons.get_lesson(token, lesson_id)
            lesson_gen.request_outline(lesson_id, settings, body.augmentation)
            return JSONResponse(
                status_code=200,
                content=lessons.get_lesson(token, lesson_id),
            )
        return JSONResponse(
            status_code=200,
            content=lessons.save_outline(
                token,
                lesson_id,
                english=body.english,
                spanish=body.spanish,
                ai_additions=body.ai_additions,
                approve=body.approve,
            ),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/lessons/{lesson_id}/quiz")
def lesson_quiz(lesson_id: str, body: QuizIn, request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    token = _lesson_token(request)
    try:
        lessons.get_lesson(token, lesson_id)
        if body.generate:
            lesson_gen.generate_quiz_now(
                lesson_id,
                settings,
                count=body.count,
                formats=body.formats,
            )
            return JSONResponse(status_code=200, content=lessons.get_lesson(token, lesson_id))
        return JSONResponse(
            status_code=200,
            content=lessons.save_quiz(
                token,
                lesson_id,
                {
                    "english": body.english,
                    "spanish": body.spanish,
                    "items": body.items,
                },
                approve=body.approve,
            ),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/lessons/{lesson_id}/publish")
def lesson_publish(lesson_id: str, body: PublishIn, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=lessons.publish_lesson(
                _lesson_token(request),
                lesson_id,
                include_transcript=body.include_transcript,
                expires_hours=body.expires_hours,
            ),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.post("/api/v1/lessons/{lesson_id}/unpublish")
def lesson_unpublish(lesson_id: str, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=lessons.revoke_publication(_lesson_token(request), lesson_id),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.delete("/api/v1/lessons/{lesson_id}")
def lesson_delete(lesson_id: str, request: Request) -> JSONResponse:
    try:
        return JSONResponse(
            status_code=200,
            content=lessons.delete_lesson(_lesson_token(request), lesson_id),
        )
    except ClassError as exc:
        return _class_error(exc)


@router.get("/api/v1/share/{share_token}")
def lesson_share(share_token: str) -> JSONResponse:
    try:
        return JSONResponse(status_code=200, content=lessons.get_shared(share_token))
    except ClassError as exc:
        return _class_error(exc)


@router.get("/api/v1/session")
def session() -> dict[str, object]:
    """Phase 1 skeleton. Email codes are not connected, so this never creates a session."""
    return {
        "authenticated": False,
        "method": "email_otp",
        "configured": False,
        "detail": "Email codes are not connected. No session was created.",
    }


@router.get("/api/v1/entitlement")
def entitlement(request: Request) -> dict[str, object]:
    """Phase 1 skeleton. Reports that no subscription exists. Does not call Stripe."""
    settings: Settings = request.app.state.settings
    plan = load_plan(settings.plan_path)
    return {
        "status": "none",
        "billing_implemented": False,
        "production_billing_enabled": settings.production_billing_enabled,
        "trial_days": plan["trial_days"],
        "price_cents": plan["amount_cents"],
        "currency": plan["currency"],
        "student_price_cents": 0,
        "detail": "No subscription exists. Checkout is not connected.",
    }

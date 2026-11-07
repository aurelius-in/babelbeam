"""FastAPI application factory. Importing this module validates startup settings."""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
for _runtime in (
    _here.parents[1] / "packages" / "runtime",
    _here.parents[3] / "packages" / "runtime",
):
    if _runtime.is_dir() and str(_runtime) not in sys.path:
        sys.path.insert(0, str(_runtime))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.routes import router  # noqa: E402
from babelbeam_runtime import Settings, validate_settings  # noqa: E402
from babelbeam_runtime.config import allowed_origins  # noqa: E402


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else Settings()
    validate_settings(resolved)
    app = FastAPI(title="BabelBeam API", version="0.1.0")
    app.state.settings = resolved
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(resolved),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Class-Token", "X-Lesson-Token"],
    )
    app.include_router(router)

    @app.on_event("startup")
    def _start_lesson_jobs() -> None:
        from app.lesson_gen import ensure_outline_worker

        ensure_outline_worker(resolved)

    return app


app = create_app()

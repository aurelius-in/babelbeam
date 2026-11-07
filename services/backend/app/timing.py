"""Request stage timing. Records stage names, milliseconds, and byte sizes only.

Nothing spoken, translated, or identifying is ever passed to this module.
"""

from __future__ import annotations

import contextvars
import re
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class StageTimer:
    def __init__(self, route: str) -> None:
        self.route = _safe(route)
        self._started = time.perf_counter()
        self._stages: list[tuple[str, int]] = []
        self._sizes: dict[str, int] = {}
        self._lock = threading.Lock()

    def add(self, stage: str, ms: int) -> None:
        with self._lock:
            self._stages.append((_safe(stage), max(0, int(ms))))

    def size(self, name: str, value: int) -> None:
        with self._lock:
            self._sizes[_safe(name)] = max(0, int(value))

    def total_ms(self) -> int:
        return round((time.perf_counter() - self._started) * 1000)

    def stages(self) -> list[tuple[str, int]]:
        with self._lock:
            return list(self._stages)

    def server_timing(self) -> str:
        entries = [f"{name};dur={ms}" for name, ms in self.stages()]
        entries.append(f"total;dur={self.total_ms()}")
        return ", ".join(entries)

    def log_line(self, status: int) -> str:
        with self._lock:
            stages = " ".join(f"{name}={ms}" for name, ms in self._stages)
            sizes = " ".join(f"{name}_bytes={value}" for name, value in self._sizes.items())
        parts = [f"bb_timing route={self.route} status={int(status)}", stages, sizes]
        parts.append(f"total={self.total_ms()}")
        return " ".join(part for part in parts if part)


_CURRENT: contextvars.ContextVar[StageTimer | None] = contextvars.ContextVar(
    "babelbeam_stage_timer", default=None
)


def _safe(name: str) -> str:
    return name if _NAME.match(name) else "stage"


def current() -> StageTimer | None:
    return _CURRENT.get()


@contextmanager
def request_timer(route: str) -> Iterator[StageTimer]:
    timer = StageTimer(route)
    token = _CURRENT.set(timer)
    try:
        yield timer
    finally:
        _CURRENT.reset(token)


@contextmanager
def stage(name: str) -> Iterator[None]:
    timer = _CURRENT.get()
    started = time.perf_counter()
    try:
        yield
    finally:
        if timer is not None:
            timer.add(name, round((time.perf_counter() - started) * 1000))


def record_size(name: str, value: int) -> None:
    timer = _CURRENT.get()
    if timer is not None:
        timer.size(name, value)


def emit(timer: StageTimer, status: int) -> None:
    print(timer.log_line(status), file=sys.stdout, flush=True)

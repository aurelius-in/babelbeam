"""Class and floor vocabularies from the product spec. Transitions are explicit."""

from __future__ import annotations

from enum import StrEnum


class ClassState(StrEnum):
    DRAFT = "DRAFT"
    STARTING = "STARTING"
    READY = "READY"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    ENDING = "ENDING"
    ENDED = "ENDED"
    FAILED = "FAILED"


class FloorState(StrEnum):
    IDLE = "IDLE"
    REQUESTED = "REQUESTED"
    GRANTING = "GRANTING"
    GRANTED = "GRANTED"
    SPEAKING = "SPEAKING"
    DRAINING = "DRAINING"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"
    REVOKED = "REVOKED"
    DISCONNECTED = "DISCONNECTED"


CLASS_TRANSITIONS: dict[ClassState, frozenset[ClassState]] = {
    ClassState.DRAFT: frozenset({ClassState.STARTING}),
    ClassState.STARTING: frozenset({ClassState.READY, ClassState.FAILED}),
    ClassState.READY: frozenset({ClassState.LIVE, ClassState.FAILED}),
    ClassState.LIVE: frozenset({ClassState.PAUSED, ClassState.DEGRADED, ClassState.ENDING}),
    ClassState.PAUSED: frozenset({ClassState.LIVE, ClassState.ENDING}),
    ClassState.DEGRADED: frozenset({ClassState.LIVE, ClassState.ENDING, ClassState.FAILED}),
    ClassState.ENDING: frozenset({ClassState.ENDED}),
    ClassState.ENDED: frozenset(),
    ClassState.FAILED: frozenset(),
}

FLOOR_TRANSITIONS: dict[FloorState, frozenset[FloorState]] = {
    FloorState.IDLE: frozenset({FloorState.REQUESTED}),
    FloorState.REQUESTED: frozenset(
        {FloorState.GRANTING, FloorState.REJECTED, FloorState.TIMED_OUT}
    ),
    FloorState.GRANTING: frozenset(
        {FloorState.GRANTED, FloorState.REVOKED, FloorState.DISCONNECTED}
    ),
    FloorState.GRANTED: frozenset(
        {FloorState.SPEAKING, FloorState.TIMED_OUT, FloorState.REVOKED, FloorState.DISCONNECTED}
    ),
    FloorState.SPEAKING: frozenset(
        {FloorState.DRAINING, FloorState.REVOKED, FloorState.DISCONNECTED}
    ),
    FloorState.DRAINING: frozenset({FloorState.RELEASED, FloorState.REVOKED}),
    FloorState.RELEASED: frozenset({FloorState.IDLE}),
    FloorState.REJECTED: frozenset({FloorState.IDLE}),
    FloorState.TIMED_OUT: frozenset({FloorState.IDLE}),
    FloorState.REVOKED: frozenset({FloorState.IDLE}),
    FloorState.DISCONNECTED: frozenset({FloorState.IDLE}),
}


def assert_transition(current: ClassState | FloorState, nxt: ClassState | FloorState) -> None:
    if isinstance(current, ClassState) and isinstance(nxt, ClassState):
        if nxt not in CLASS_TRANSITIONS[current]:
            raise ValueError(f"Illegal transition {current.value} -> {nxt.value}.")
        return
    if isinstance(current, FloorState) and isinstance(nxt, FloorState):
        if nxt not in FLOOR_TRANSITIONS[current]:
            raise ValueError(f"Illegal transition {current.value} -> {nxt.value}.")
        return
    raise ValueError("Class and floor states cannot transition into each other.")

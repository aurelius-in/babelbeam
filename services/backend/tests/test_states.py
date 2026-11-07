from __future__ import annotations

import pytest

from babelbeam_runtime import ClassState, FloorState, assert_transition


def test_class_can_go_live_and_end() -> None:
    assert_transition(ClassState.DRAFT, ClassState.STARTING)
    assert_transition(ClassState.STARTING, ClassState.READY)
    assert_transition(ClassState.READY, ClassState.LIVE)
    assert_transition(ClassState.LIVE, ClassState.ENDING)
    assert_transition(ClassState.ENDING, ClassState.ENDED)


def test_ended_class_cannot_restart() -> None:
    with pytest.raises(ValueError, match="Illegal transition"):
        assert_transition(ClassState.ENDED, ClassState.LIVE)


def test_floor_requires_an_explicit_grant_before_speech() -> None:
    with pytest.raises(ValueError, match="Illegal transition"):
        assert_transition(FloorState.IDLE, FloorState.SPEAKING)
    assert_transition(FloorState.IDLE, FloorState.REQUESTED)
    assert_transition(FloorState.REQUESTED, FloorState.GRANTING)
    assert_transition(FloorState.GRANTING, FloorState.GRANTED)
    assert_transition(FloorState.GRANTED, FloorState.SPEAKING)


def test_draining_is_distinct_from_revoke() -> None:
    assert_transition(FloorState.SPEAKING, FloorState.DRAINING)
    assert_transition(FloorState.DRAINING, FloorState.RELEASED)
    assert_transition(FloorState.SPEAKING, FloorState.REVOKED)
    with pytest.raises(ValueError, match="Illegal transition"):
        assert_transition(FloorState.DRAINING, FloorState.SPEAKING)

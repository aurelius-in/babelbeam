"""Merge class board snapshots written by concurrent requests. Pure functions, no I/O.

Each write stores a whole new snapshot. Two requests that load the same snapshot and
write at the same time would otherwise drop each other's changes. Readers merge the
recent snapshots instead: grow-only lists (student tokens, segments, cues) are unions,
an ended class stays ended, and any other room field takes the newest written value.
"""

from __future__ import annotations

from typing import Any

Board = dict[str, Any]
Room = dict[str, Any]
Item = dict[str, Any]

GROW_ONLY_LISTS = ("segments", "cues")
PENDING_AUDIO = "pending"


def merge_snapshots(snapshots: list[Board]) -> Board:
    """Merge snapshots ordered oldest to newest."""
    rooms: dict[str, Room] = {}
    order: list[str] = []
    for snapshot in snapshots:
        listed = snapshot.get("rooms") if isinstance(snapshot, dict) else None
        if not isinstance(listed, list):
            continue
        for room in listed:
            if not isinstance(room, dict) or not isinstance(room.get("id"), str):
                continue
            key = room["id"]
            if key in rooms:
                rooms[key] = merge_room(rooms[key], room)
            else:
                rooms[key] = merge_room({}, room)
                order.append(key)
    return {"rooms": [rooms[key] for key in order]}


def merge_room(older: Room, newer: Room) -> Room:
    merged: Room = {**older, **newer}
    merged["student_tokens"] = _union_strings(
        older.get("student_tokens"), newer.get("student_tokens")
    )
    merged["student_voices"] = _merge_voices(
        older.get("student_voices"), newer.get("student_voices")
    )
    merged["student_names"] = _merge_voices(
        older.get("student_names"), newer.get("student_names")
    )
    merged["student_genders"] = _merge_voices(
        older.get("student_genders"), newer.get("student_genders")
    )
    merged["student_upload_until"] = _merge_upload_locks(
        older.get("student_upload_until"), newer.get("student_upload_until")
    )
    if older.get("status") == "ended" or newer.get("status") == "ended":
        merged["status"] = "ended"
        merged["ended_at"] = _latest(older.get("ended_at"), newer.get("ended_at"))
        for name in GROW_ONLY_LISTS:
            merged[name] = []
        merged["student_turn_until"] = None
        merged["student_voices"] = {}
        merged["student_names"] = {}
        merged["student_genders"] = {}
        merged["student_upload_until"] = {}
        return merged
    for name in GROW_ONLY_LISTS:
        merged[name] = merge_items(older.get(name), newer.get(name))
    return merged


def merge_items(older: object, newer: object) -> list[Item]:
    """Union by id. Order by first append time, then by first appearance."""
    chosen: dict[str, Item] = {}
    first_seen: dict[str, int] = {}
    position = 0
    for source in (older, newer):
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            key = item["id"]
            if key in chosen:
                chosen[key] = _prefer(chosen[key], item)
            else:
                chosen[key] = item
                first_seen[key] = position
                position += 1
    ordered = sorted(chosen, key=lambda key: (_appended(chosen[key]), first_seen[key]))
    return [chosen[key] for key in ordered]


def _prefer(current: Item, candidate: Item) -> Item:
    """A finished copy beats a copy still waiting for audio. Otherwise the newer copy wins."""
    current_pending = current.get("audio_state") == PENDING_AUDIO
    candidate_pending = candidate.get("audio_state") == PENDING_AUDIO
    if candidate_pending and not current_pending:
        chosen = current
    elif not candidate_pending and not current_pending:
        current_clips = current.get("clips") if isinstance(current.get("clips"), dict) else {}
        candidate_clips = (
            candidate.get("clips") if isinstance(candidate.get("clips"), dict) else {}
        )
        chosen = current if len(current_clips) > len(candidate_clips) else candidate
    else:
        chosen = candidate
    # A listened flag must survive a concurrent write of the same question.
    if current.get("listened") or candidate.get("listened"):
        chosen = {**chosen, "listened": True}
    if current.get("student_name") and not chosen.get("student_name"):
        chosen = {**chosen, "student_name": current.get("student_name")}
    elif candidate.get("student_name") and not chosen.get("student_name"):
        chosen = {**chosen, "student_name": candidate.get("student_name")}
    return chosen


def _merge_upload_locks(older: object, newer: object) -> dict[str, float]:
    merged: dict[str, float] = {}
    for source in (older, newer):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if isinstance(key, str) and isinstance(value, int | float) and key:
                prior = merged.get(key)
                merged[key] = float(value) if prior is None else max(prior, float(value))
    return merged


def _appended(item: Item) -> int:
    value = item.get("appended_ns")
    return value if isinstance(value, int) and value > 0 else 0


def _merge_voices(older: object, newer: object) -> dict[str, str]:
    merged: dict[str, str] = {}
    for source in (older, newer):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if isinstance(key, str) and isinstance(value, str) and key and value:
                merged[key] = value
    return merged


def _union_strings(older: object, newer: object) -> list[str]:
    seen: list[str] = []
    for source in (older, newer):
        if not isinstance(source, list):
            continue
        for value in source:
            if isinstance(value, str) and value not in seen:
                seen.append(value)
    return seen


def _latest(first: object, second: object) -> float | None:
    values = [value for value in (first, second) if isinstance(value, int | float)]
    return float(max(values)) if values else None

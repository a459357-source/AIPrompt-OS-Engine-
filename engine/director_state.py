"""
director_state.py — V5.2 Director State Machine (Phase B)
==========================================================
Persistent lifecycle state for Event Director nodes.
"""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import config
from engine import io_utils
from engine.event_director import DirectorPlan

logger = logging.getLogger(__name__)

PENDING = "PENDING"
ACTIVE = "ACTIVE"
RESOLVED = "RESOLVED"
FAILED = "FAILED"
COOLDOWN = "COOLDOWN"

DIRECTOR_EVENT_STATES = frozenset({PENDING, ACTIVE, RESOLVED, FAILED, COOLDOWN})


@dataclass
class DirectorEventState:
    """Lifecycle record for a single director event instance."""

    instance_id: str
    event_id: str
    category: str
    state: str
    priority: int
    reason: str
    participants: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    started_turn: int = 0
    last_turn: int = 0
    turns_active: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict | None) -> DirectorEventState | None:
        if not isinstance(raw, dict):
            return None
        state = str(raw.get("state", PENDING))
        if state not in DIRECTOR_EVENT_STATES:
            state = PENDING
        return cls(
            instance_id=str(raw.get("instance_id", "")).strip() or _new_instance_id(),
            event_id=str(raw.get("event_id", "")).strip(),
            category=str(raw.get("category", "unknown")),
            state=state,
            priority=max(0, min(100, int(raw.get("priority", 0) or 0))),
            reason=str(raw.get("reason", "")),
            participants=[
                str(p) for p in (raw.get("participants") or []) if str(p).strip()
            ],
            tags=[str(t) for t in (raw.get("tags") or []) if str(t).strip()],
            started_turn=int(raw.get("started_turn", 0) or 0),
            last_turn=int(raw.get("last_turn", 0) or 0),
            turns_active=int(raw.get("turns_active", 0) or 0),
        )

    @classmethod
    def from_plan(
        cls,
        plan: DirectorPlan,
        *,
        state: str = PENDING,
        turn: int = 0,
    ) -> DirectorEventState:
        return cls(
            instance_id=_new_instance_id(),
            event_id=plan.event_id,
            category=plan.category,
            state=state,
            priority=plan.priority,
            reason=plan.reason,
            participants=list(plan.participants),
            tags=list(plan.tags),
            started_turn=turn,
            last_turn=turn,
            turns_active=0 if state != ACTIVE else 1,
        )


def _new_instance_id() -> str:
    return uuid.uuid4().hex[:12]


def empty_director_state() -> dict:
    return {
        "version": 2,
        "current_event": None,
        "pending": [],
        "lifecycle": [],
    }


def load_director_state() -> dict:
    try:
        data = io_utils.read_json(config.DIRECTOR_STATE_PATH)
        if isinstance(data, dict):
            return normalize_director_state(data)
    except Exception:
        pass
    return empty_director_state()


def save_director_state(state: dict, *, persist: bool = True) -> None:
    if not persist:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.DIRECTOR_STATE_PATH, normalize_director_state(state))


def normalize_director_state(raw: dict | None) -> dict:
    state = empty_director_state()
    if not isinstance(raw, dict):
        return state

    current = DirectorEventState.from_dict(raw.get("current_event"))
    state["current_event"] = current.to_dict() if current and current.event_id else None

    pending: list[dict] = []
    for item in raw.get("pending") or []:
        inst = DirectorEventState.from_dict(item)
        if inst and inst.event_id and inst.state == PENDING:
            pending.append(inst.to_dict())
    state["pending"] = pending[: config.DIRECTOR_MAX_PENDING]

    lifecycle: list[dict] = []
    for item in raw.get("lifecycle") or []:
        inst = DirectorEventState.from_dict(item)
        if inst and inst.event_id:
            lifecycle.append(inst.to_dict())
    state["lifecycle"] = lifecycle[-100:]
    return state


def get_current_event(state: dict) -> DirectorEventState | None:
    return DirectorEventState.from_dict(state.get("current_event"))


def set_current_event(state: dict, event: DirectorEventState | None) -> dict:
    state = copy.deepcopy(state) if state else empty_director_state()
    state["current_event"] = event.to_dict() if event and event.event_id else None
    return state


def get_pending_events(state: dict) -> list[DirectorEventState]:
    out: list[DirectorEventState] = []
    for item in state.get("pending") or []:
        inst = DirectorEventState.from_dict(item)
        if inst and inst.event_id:
            out.append(inst)
    return out


def set_pending_events(state: dict, events: list[DirectorEventState]) -> dict:
    state = copy.deepcopy(state) if state else empty_director_state()
    state["pending"] = [
        e.to_dict() for e in events[: config.DIRECTOR_MAX_PENDING] if e.event_id
    ]
    return state


def append_lifecycle(state: dict, event: DirectorEventState) -> dict:
    state = copy.deepcopy(state) if state else empty_director_state()
    lifecycle = state.setdefault("lifecycle", [])
    lifecycle.append(event.to_dict())
    if len(lifecycle) > 100:
        state["lifecycle"] = lifecycle[-100:]
    return state


def transition_event(
    event: DirectorEventState,
    new_state: str,
    *,
    turn: int,
) -> DirectorEventState:
    if new_state not in DIRECTOR_EVENT_STATES:
        raise ValueError(f"invalid director state: {new_state}")
    updated = copy.deepcopy(event)
    updated.state = new_state
    updated.last_turn = turn
    if new_state == ACTIVE and updated.turns_active <= 0:
        updated.turns_active = 1
    return updated


def activate_event(event: DirectorEventState, turn: int) -> DirectorEventState:
    updated = transition_event(event, ACTIVE, turn=turn)
    if updated.started_turn <= 0:
        updated.started_turn = turn
    updated.turns_active = max(1, updated.turns_active)
    return updated


def bump_active_turn(event: DirectorEventState, turn: int) -> DirectorEventState:
    updated = copy.deepcopy(event)
    updated.last_turn = turn
    updated.turns_active = max(1, updated.turns_active + 1)
    return updated

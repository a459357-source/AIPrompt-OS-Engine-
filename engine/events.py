"""
events.py — World Events System
=================================
Manages scheduled and conditional world events that drive the plot
independently of player actions.  Events flow through:
  pending → active → resolved (or expired)

Data model (memory.json → world_events):
  [
    {
      "id": "evt_001",
      "title": "广场协议签署",
      "description": "五国财长在纽约签署广场协议...",
      "status": "pending",        # pending | active | resolved | expired
      "related_factions": ["华尔街资本", "日本大藏省"],
      "related_characters": ["近卫诚一郎"],
      "importance": 90,           # 1-100
      "trigger_turn": 5,          # turn when it becomes active
      "resolved_turn": null,
      "effects": {}               # reserved for future conditional effects
    }
  ]
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Public API ──────────────────────────────────────────────────────

def init_events(memory: dict) -> None:
    """Ensure the world_events list exists in memory."""
    memory.setdefault("world_events", [])


def schedule_event(
    memory: dict,
    title: str,
    description: str = "",
    trigger_turn: int = 0,
    related_factions: list[str] | None = None,
    related_characters: list[str] | None = None,
    importance: int = 50,
    event_id: str | None = None,
) -> str:
    """
    Add a pending world event.  Returns the event id.

    If trigger_turn is 0, the event triggers immediately (next turn).
    """
    if event_id is None:
        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
        event_id = f"evt_{ts}"

    events = memory.setdefault("world_events", [])

    # Don't duplicate
    for e in events:
        if e.get("id") == event_id:
            return event_id

    events.append({
        "id": event_id,
        "title": title,
        "description": description,
        "status": "pending",
        "related_factions": related_factions or [],
        "related_characters": related_characters or [],
        "importance": max(1, min(100, importance)),
        "trigger_turn": trigger_turn,
        "resolved_turn": None,
        "created_at": datetime.now().isoformat(),
    })
    logger.info("Events: scheduled '%s' (id=%s, trigger_turn=%d)", title, event_id, trigger_turn)
    return event_id


def check_event_triggers(memory: dict, turn: int) -> list[dict]:
    """
    Activate any pending events whose trigger_turn has arrived.
    Returns list of newly activated events.
    """
    events = memory.get("world_events", [])
    triggered: list[dict] = []

    for e in events:
        if e.get("status") != "pending":
            continue
        trigger = e.get("trigger_turn", 0)
        if trigger > 0 and turn >= trigger:
            e["status"] = "active"
            triggered.append(e)
            logger.info("Events: activated '%s' (turn %d)", e.get("title"), turn)

    return triggered


def resolve_event(memory: dict, event_id: str, turn: int = 0) -> bool:
    """Mark an active event as resolved."""
    events = memory.get("world_events", [])
    for e in events:
        if e.get("id") == event_id and e.get("status") == "active":
            e["status"] = "resolved"
            e["resolved_turn"] = turn or e.get("trigger_turn", 0)
            logger.info("Events: resolved '%s' (turn %d)", e.get("title"), turn)
            return True
    return False


def expire_event(memory: dict, event_id: str) -> bool:
    """Mark an event as expired (missed the window)."""
    events = memory.get("world_events", [])
    for e in events:
        if e.get("id") == event_id and e.get("status") in ("pending", "active"):
            e["status"] = "expired"
            logger.info("Events: expired '%s'", e.get("title"))
            return True
    return False


def get_active_events(memory: dict) -> list[dict]:
    """Return currently active events, sorted by importance descending."""
    events = memory.get("world_events", [])
    active = [e for e in events if e.get("status") == "active"]
    active.sort(key=lambda e: e.get("importance", 0), reverse=True)
    return active


def get_pending_events(memory: dict) -> list[dict]:
    """Return pending events, sorted by trigger_turn ascending."""
    events = memory.get("world_events", [])
    pending = [e for e in events if e.get("status") == "pending"]
    pending.sort(key=lambda e: e.get("trigger_turn", 999))
    return pending


def get_event_context(memory: dict) -> str:
    """
    Build a prompt-ready summary of active and imminent events.
    Injects faction/character-relevant hooks for the AI to incorporate.
    """
    active = get_active_events(memory)
    pending = get_pending_events(memory)

    if not active and not pending:
        return ""

    lines: list[str] = ["【世界事件】"]

    if active:
        lines.append("  ⚡ 正在发生：")
        for e in active[:3]:  # top 3 by importance
            desc = e.get("description", "")[:80]
            factions = e.get("related_factions", [])
            chars = e.get("related_characters", [])
            extra = ""
            if factions:
                extra += f" 涉及势力: {', '.join(factions)}"
            if chars:
                extra += f" 涉及角色: {', '.join(chars)}"
            lines.append(f"  • {e['title']}")
            if desc:
                lines.append(f"    {desc}")
            if extra:
                lines.append(f"    {extra}")

    if pending:
        lines.append("  🔮 即将发生：")
        for e in pending[:3]:
            trigger = e.get("trigger_turn", "?")
            lines.append(f"  • [T{trigger}] {e['title']}")

    return "\n".join(lines)


# ── Event seeding ───────────────────────────────────────────────────

def seed_default_events(memory: dict, world_pack: dict | None = None) -> list[str]:
    """
    Auto-generate default events from world_pack faction goals.
    Each faction's first goal becomes a scheduled event at turn ~5-20.

    Uses a deterministic seed derived from the world title so that
    event trigger turns are reproducible across runs — saves created
    under the same world pack will see the same event schedule.

    Returns list of created event IDs.
    """
    import random
    import hashlib

    created: list[str] = []
    if not world_pack:
        return created

    # Deterministic seed from world title — same world = same events
    world_title = world_pack.get("world", {}).get("title", "Galgame")
    seed = int(hashlib.md5(world_title.encode()).hexdigest()[:8], 16) % (2**31)
    rng = random.Random(seed)

    factions = world_pack.get("world", {}).get("factions", [])
    for f in factions:
        goals = f.get("goals", [])
        if not goals:
            continue
        # Schedule the first goal as an event
        name = f.get("name", "?")
        trigger = rng.randint(3, 15)
        eid = schedule_event(
            memory,
            title=f"{name}：{goals[0]}",
            description=f"{name} 正在推进其核心目标。",
            trigger_turn=trigger,
            related_factions=[name],
            importance=f.get("influence", 50),
        )
        created.append(eid)

    return created

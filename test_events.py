"""
Tests for events.py — Event scheduling, triggering, and deterministic seeding.
Run: python prompt-os-engine/test_events.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from engine.events import (
    init_events, schedule_event, check_event_triggers,
    resolve_event, expire_event, get_active_events,
    get_pending_events, seed_default_events,
)


def _fresh_memory() -> dict:
    mem: dict = {}
    init_events(mem)
    return mem


def test_init_events():
    """init_events should create an empty world_events list."""
    mem = {}
    init_events(mem)
    assert "world_events" in mem
    assert mem["world_events"] == []
    print("✅ init_events: PASS")


def test_schedule_event():
    """schedule_event should add a pending event with a unique ID."""
    mem = _fresh_memory()
    eid = schedule_event(mem, "测试事件", "描述", trigger_turn=5)
    assert eid, "Expected an event ID"
    assert len(mem["world_events"]) == 1
    evt = mem["world_events"][0]
    assert evt["status"] == "pending"
    assert evt["trigger_turn"] == 5
    print(f"✅ schedule_event: PASS — id={eid}")


def test_schedule_event_no_duplicate():
    """schedule_event should not duplicate events with the same ID."""
    mem = _fresh_memory()
    eid = schedule_event(mem, "事件A", trigger_turn=3, event_id="evt_test")
    eid2 = schedule_event(mem, "事件A again", trigger_turn=5, event_id="evt_test")
    assert eid == eid2
    assert len(mem["world_events"]) == 1, \
        f"Expected 1 event, got {len(mem['world_events'])}"
    print("✅ schedule_event no-duplicate: PASS")


def test_check_event_triggers():
    """check_event_triggers should activate events when turn >= trigger_turn."""
    mem = _fresh_memory()
    schedule_event(mem, "早发事件", trigger_turn=3)
    schedule_event(mem, "晚发事件", trigger_turn=10)

    # Turn 2 — nothing should trigger
    triggered = check_event_triggers(mem, 2)
    assert len(triggered) == 0, f"Expected 0 triggers, got {len(triggered)}"

    # Turn 5 — first event should trigger
    triggered = check_event_triggers(mem, 5)
    assert len(triggered) == 1
    assert triggered[0]["title"] == "早发事件"
    assert triggered[0]["status"] == "active"
    print("✅ check_event_triggers: PASS")


def test_resolve_event():
    """resolve_event should mark an active event as resolved."""
    mem = _fresh_memory()
    schedule_event(mem, "可解决事件", trigger_turn=1)
    check_event_triggers(mem, 1)

    assert resolve_event(mem, mem["world_events"][0]["id"], turn=2)
    assert mem["world_events"][0]["status"] == "resolved"
    assert mem["world_events"][0]["resolved_turn"] == 2
    print("✅ resolve_event: PASS")


def test_expire_event():
    """expire_event should mark a pending/active event as expired."""
    mem = _fresh_memory()
    eid = schedule_event(mem, "过期事件", trigger_turn=5)
    assert expire_event(mem, eid)
    assert mem["world_events"][0]["status"] == "expired"
    print("✅ expire_event: PASS")


def test_get_active_events():
    """get_active_events should return events sorted by importance descending."""
    mem = _fresh_memory()
    schedule_event(mem, "低优先", trigger_turn=1, importance=30)
    schedule_event(mem, "高优先", trigger_turn=1, importance=90)
    check_event_triggers(mem, 1)

    active = get_active_events(mem)
    assert len(active) == 2
    assert active[0]["title"] == "高优先"  # highest importance first
    print("✅ get_active_events: PASS")


def test_get_pending_events():
    """get_pending_events should return pending events sorted by trigger_turn."""
    mem = _fresh_memory()
    schedule_event(mem, "远事件", trigger_turn=20)
    schedule_event(mem, "近事件", trigger_turn=5)

    pending = get_pending_events(mem)
    assert len(pending) == 2
    assert pending[0]["title"] == "近事件"  # earliest trigger first
    print("✅ get_pending_events: PASS")


def test_seed_default_events_deterministic():
    """seed_default_events should produce the same trigger turns for the same world."""
    world_pack = {
        "world": {
            "title": "测试世界",
            "factions": [
                {"name": "势力A", "goals": ["目标A1"], "influence": 50},
                {"name": "势力B", "goals": ["目标B1"], "influence": 60},
            ]
        }
    }

    mem1: dict = {}
    init_events(mem1)
    seed_default_events(mem1, world_pack)

    mem2: dict = {}
    init_events(mem2)
    seed_default_events(mem2, world_pack)

    # Same world should produce same triggers
    t1 = [e["trigger_turn"] for e in mem1["world_events"]]
    t2 = [e["trigger_turn"] for e in mem2["world_events"]]
    assert t1 == t2, f"Expected deterministic triggers, got {t1} vs {t2}"
    print(f"✅ seed_default_events deterministic: PASS — triggers: {t1}")


if __name__ == "__main__":
    tests = [
        test_init_events,
        test_schedule_event,
        test_schedule_event_no_duplicate,
        test_check_event_triggers,
        test_resolve_event,
        test_expire_event,
        test_get_active_events,
        test_get_pending_events,
        test_seed_default_events_deterministic,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {e}")
        except Exception as e:
            print(f"💥 ERROR in {test.__name__}: {e}")
    print(f"\n🎉 {passed}/{len(tests)} tests passed!")
    sys.exit(0 if passed == len(tests) else 1)

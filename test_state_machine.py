"""
Quick smoke-test for the state machine logic.
Run: python prompt-os-engine/test_state_machine.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine.state_manager import _merge_and_enforce, _level_idx
from engine.builder import _detect_force_event


def test_climax_to_cooldown():
    """Verify CLIMAX → COOLDOWN is enforced."""
    current = {
        "turn": 2,
        "scene": "遗迹核心",
        "status": "CLIMAX",
        "characters": {
            "A": {"name": "林夜", "role": "船长", "level": "L3", "relation": "信任"},
        },
        "history": [],
    }
    # AI tries to propose BUILD (wrong!) after CLIMAX
    proposed = {"status": "BUILD", "scene": "某处"}
    result = _merge_and_enforce(current, proposed)

    assert result["status"] == "COOLDOWN", \
        f"Expected COOLDOWN after CLIMAX, got {result['status']}"
    print("✅ CLIMAX → COOLDOWN enforcement: PASS")


def test_status_never_backward():
    """Verify status cannot regress."""
    current = {
        "turn": 3,
        "scene": "舰桥",
        "status": "TENSION",
        "characters": {},
        "history": [],
    }
    proposed = {"status": "SETUP"}  # backward
    result = _merge_and_enforce(current, proposed)
    assert result["status"] == "TENSION", \
        f"Expected TENSION (no regress), got {result['status']}"
    print("✅ Status no-regress: PASS")


def test_interaction_never_decrease():
    """Verify interaction level cannot drop."""
    current = {
        "turn": 1,
        "scene": "舰桥",
        "status": "BUILD",
        "characters": {
            "A": {"level": "L2"},
        },
        "history": [],
    }
    proposed = {
        "status": "BUILD",
        "characters": {
            "A": {"level": "L0"},  # AI tries to drop level
        },
    }
    result = _merge_and_enforce(current, proposed)
    assert result["characters"]["A"]["level"] == "L2", \
        f"Expected L2 (no decrease), got {result['characters']['A']['level']}"
    print("✅ Interaction no-decrease: PASS")


def test_force_event_same_status():
    """Verify same-status stagnation triggers force event."""
    state = {
        "scene": "舰桥",
        "status": "SETUP",
        "turn": 2,
        "characters": {"A": {"level": "L0"}},
        "history": [
            {"turn": 0, "scene": "舰桥", "status": "SETUP", "characters": {"A": {"level": "L0"}}},
            {"turn": 1, "scene": "舰桥", "status": "SETUP", "characters": {"A": {"level": "L0"}}},
        ],
    }
    triggered, reason = _detect_force_event(state)
    assert triggered, f"Expected force event triggered, got {triggered}"
    assert "状态 SETUP" in reason, f"Expected status stagnation reason, got: {reason}"
    print(f"✅ Force event (same status): PASS — {reason}")


def test_force_event_same_scene():
    """Verify same-scene stagnation triggers force event."""
    state = {
        "scene": "舰桥",
        "status": "BUILD",
        "turn": 3,
        "characters": {"A": {"level": "L1"}},
        "history": [
            {"turn": 0, "scene": "舰桥", "status": "SETUP", "characters": {"A": {"level": "L0"}}},
            {"turn": 1, "scene": "舰桥", "status": "BUILD",  "characters": {"A": {"level": "L0"}}},
            {"turn": 2, "scene": "舰桥", "status": "BUILD",  "characters": {"A": {"level": "L1"}}},
        ],
    }
    triggered, reason = _detect_force_event(state)
    assert triggered, f"Expected force event triggered, got {triggered}"
    assert "同场景" in reason, f"Expected same-scene reason, got: {reason}"
    print(f"✅ Force event (same scene): PASS — {reason}")


def test_turn_increment():
    """Verify turn always increments by 1."""
    current = {"turn": 5, "scene": "X", "status": "SETUP", "characters": {}, "history": []}
    proposed = {"status": "SETUP"}
    result = _merge_and_enforce(current, proposed)
    assert result["turn"] == 6, f"Expected turn 6, got {result['turn']}"
    print("✅ Turn increment: PASS")


def test_merge_duplicate_name_character():
    """AI registering 诺亚 under name key merges into letter key A."""
    current = {
        "turn": 1,
        "scene": "森林",
        "status": "BUILD",
        "characters": {
            "A": {"name": "诺亚", "role": "骑士", "level": "L1", "relation": "死敌"},
        },
        "history": [],
    }
    proposed = {
        "status": "BUILD",
        "characters": {
            "诺亚": {"name": "诺亚", "role": "主角", "level": "L2", "relation": "主角"},
        },
    }
    result = _merge_and_enforce(current, proposed)
    assert "诺亚" not in result["characters"]
    assert result["characters"]["A"]["relation"] == "主角"
    assert result["characters"]["A"]["level"] == "L2"
    print("✅ Merge duplicate name: PASS")


if __name__ == "__main__":
    tests = [
        test_climax_to_cooldown,
        test_status_never_backward,
        test_interaction_never_decrease,
        test_force_event_same_status,
        test_force_event_same_scene,
        test_turn_increment,
        test_merge_duplicate_name_character,
    ]
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"❌ FAIL: {e}")
            sys.exit(1)
    print("\n🎉 All state machine tests passed!")

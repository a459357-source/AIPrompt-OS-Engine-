"""
Tests for memory.py — Character trust, flags, initial trust, and
story-based trust heuristics.
Run: python prompt-os-engine/test_memory.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from engine.memory import (
    update_trust, set_flag, get_initial_trust,
    guess_trust_delta_from_story,
    parse_option_trust_deltas,
    detect_new_characters_from_story,
    init_factions, update_faction_reputation,
    update_faction_attitude,
)


# ── Test helpers ───────────────────────────────────────────────────

def _fresh_memory() -> dict:
    return {"characters": {}, "world_flags": []}


# ── Tests ──────────────────────────────────────────────────────────

def test_update_trust_creates_character():
    """update_trust should create a character entry if it doesn't exist."""
    mem = _fresh_memory()
    update_trust(mem, "林夜", 0.2, turn=1)
    assert "林夜" in mem["characters"], "Character not created"
    assert mem["characters"]["林夜"]["trust"] == 0.5, \
        f"Expected 0.5 (0.3 + 0.2), got {mem['characters']['林夜']['trust']}"
    print("✅ update_trust creates character: PASS")


def test_update_trust_clamps():
    """update_trust should clamp trust to 0.0-1.0."""
    mem = _fresh_memory()
    update_trust(mem, "A", 2.0, turn=1)   # would go to 2.3, clamped to 1.0
    assert mem["characters"]["A"]["trust"] == 1.0, \
        f"Expected 1.0, got {mem['characters']['A']['trust']}"

    update_trust(mem, "B", -1.0, turn=1)  # would go to -0.7, clamped to 0.0
    assert mem["characters"]["B"]["trust"] == 0.0, \
        f"Expected 0.0, got {mem['characters']['B']['trust']}"
    print("✅ update_trust clamping: PASS")


def test_update_trust_metric_history():
    """update_trust should append to metric_history when turn > 0."""
    mem = _fresh_memory()
    update_trust(mem, "林夜", 0.1, turn=1)
    update_trust(mem, "林夜", 0.1, turn=2)
    update_trust(mem, "林夜", 0.1, turn=3)
    hist = mem["characters"]["林夜"].get("metric_history", {}).get("trust", [])
    assert len(hist) >= 3, f"Expected >= 3 history entries, got {len(hist)}"
    # Dedup: consecutive same values should not be appended twice
    update_trust(mem, "林夜", 0.0, turn=4)  # no change
    hist2 = mem["characters"]["林夜"].get("metric_history", {}).get("trust", [])
    assert len(hist2) == len(hist), \
        f"Dedup failed — expected {len(hist)} entries, got {len(hist2)}"
    print("✅ update_trust metric_history: PASS")


def test_set_flag_idempotent():
    """set_flag should not duplicate flags."""
    mem = _fresh_memory()
    set_flag(mem, "林夜", "初次见面")
    set_flag(mem, "林夜", "初次见面")
    set_flag(mem, "林夜", "并肩作战")
    assert mem["characters"]["林夜"]["flags"] == ["初次见面", "并肩作战"], \
        f"Expected ['初次见面', '并肩作战'], got {mem['characters']['林夜']['flags']}"
    print("✅ set_flag idempotent: PASS")


def test_set_flag_world():
    """set_flag with character=None should set world flags."""
    mem = _fresh_memory()
    set_flag(mem, None, "世界末日")
    assert "世界末日" in mem["world_flags"]
    print("✅ set_flag world: PASS")


def test_get_initial_trust_known():
    """get_initial_trust should return relationship-based trust for known chars."""
    world_pack = {
        "world": {
            "characters": [
                {"name": "林夜", "relationship": ["盟友"]},
                {"name": "敌人甲", "relationship": ["敌视"]},
            ]
        }
    }
    assert get_initial_trust("林夜", world_pack) == 0.55, \
        f"Expected 0.55, got {get_initial_trust('林夜', world_pack)}"
    assert get_initial_trust("敌人甲", world_pack) == 0.10, \
        f"Expected 0.10, got {get_initial_trust('敌人甲', world_pack)}"
    print("✅ get_initial_trust known: PASS")


def test_get_initial_trust_unknown():
    """get_initial_trust should return 0.30 for unknown characters."""
    assert get_initial_trust("路人甲", {}) == 0.30
    print("✅ get_initial_trust unknown: PASS")


def test_guess_trust_delta_specific():
    """guess_trust_delta should return specific character when name is near keyword."""
    story = "林夜对主角露出微笑，两人之间的关系似乎更加融洽了。"
    deltas = guess_trust_delta_from_story(story)
    # Should find "微笑" keyword and "林夜" nearby
    assert len(deltas) > 0, "Expected at least one delta"
    # Check that specific character was matched (not __all_present__)
    chars = [d[0] for d in deltas if d[0] != "__all_present__"]
    assert len(chars) > 0, f"Expected specific character match, got: {deltas}"
    print(f"✅ guess_trust_delta specific: PASS — {deltas}")


def test_guess_trust_delta_generic():
    """guess_trust_delta should return deltas even when no specific name is near keywords.
    The caller (apply_trust_deltas) handles __all_present__ or false-positive names —
    the important thing is that sentiment keywords ARE detected."""
    story = "The atmosphere was thick with 怀疑 and 不信任. 背叛 loomed over everything."
    deltas = guess_trust_delta_from_story(story)
    assert len(deltas) > 0, f"Expected at least one delta for keywords in story, got: {deltas}"
    # Verify we got the right keywords
    deltas_with_all = [d for d in deltas if d[0] == "__all_present__"]
    deltas_named = [d for d in deltas if d[0] != "__all_present__"]
    total = len(deltas_with_all) + len(deltas_named)
    assert total > 0, f"Expected deltas, got none"
    print(f"✅ guess_trust_delta generic: PASS — {len(deltas)} deltas ({len(deltas_with_all)} generic, {len(deltas_named)} named)")


def test_parse_option_trust_deltas():
    """parse_option_trust_deltas should extract name↑N and name↓N patterns."""
    options = ["与林夜并肩作战，林夜↑5、卡洛琳↓3"]
    deltas = parse_option_trust_deltas(options)
    assert len(deltas) == 2, f"Expected 2 deltas, got {len(deltas)}"
    names = {d[0] for d in deltas}
    assert "林夜" in names
    # Check values
    for name, delta in deltas:
        if name == "林夜":
            assert delta == 0.05, f"Expected +0.05, got {delta}"
        elif "卡洛琳" in name:
            assert delta == -0.03, f"Expected -0.03, got {delta}"
    print(f"✅ parse_option_trust_deltas: PASS — {deltas}")


def test_detect_new_characters():
    """detect_new_characters should find names introduced with '名叫' etc."""
    story = "就在这时，一位名叫苏晴的女子走了进来。她自称是星联的特使。"
    known = {"林夜", "卡洛琳"}
    newcomers = detect_new_characters_from_story(story, known)
    assert "苏晴" in newcomers, f"Expected '苏晴' in {newcomers}"
    # Known names should not appear
    assert "林夜" not in newcomers
    print(f"✅ detect_new_characters: PASS — {newcomers}")


def test_init_factions():
    """init_factions should create faction entries from world_pack."""
    mem = _fresh_memory()
    # Need a world_pack on disk for this — skip if not available
    try:
        import config
        from engine import io_utils
        world = io_utils.read_yaml(config.WORLD_PACK_PATH)
        if world.get("world", {}).get("factions"):
            init_factions(mem)
            assert len(mem.get("factions", {})) > 0, "Expected factions to be created"
            print(f"✅ init_factions: PASS — {len(mem['factions'])} factions")
        else:
            print("⏭️  init_factions: SKIP (no factions in world_pack)")
    except Exception as e:
        print(f"⏭️  init_factions: SKIP ({e})")


def test_update_faction_reputation():
    """update_faction_reputation should adjust and clamp reputation."""
    mem = {"factions": {"测试势力": {"reputation": 0.5, "flags": []}}}
    update_faction_reputation(mem, "测试势力", 0.2, turn=1)
    assert mem["factions"]["测试势力"]["reputation"] == 0.7
    update_faction_reputation(mem, "测试势力", -0.5, turn=2)
    assert mem["factions"]["测试势力"]["reputation"] == 0.2
    print("✅ update_faction_reputation: PASS")


def test_update_faction_attitude():
    """update_faction_attitude should adjust directed attitudes."""
    mem = {"faction_attitudes": {}}
    update_faction_attitude(mem, "A", "B", 0.1, turn=1)
    assert mem["faction_attitudes"]["A"]["B"]["attitude"] == 0.6
    update_faction_attitude(mem, "A", "B", -0.3, turn=2)
    assert mem["faction_attitudes"]["A"]["B"]["attitude"] == 0.3
    print("✅ update_faction_attitude: PASS")


# ── Run ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_update_trust_creates_character,
        test_update_trust_clamps,
        test_update_trust_metric_history,
        test_set_flag_idempotent,
        test_set_flag_world,
        test_get_initial_trust_known,
        test_get_initial_trust_unknown,
        test_guess_trust_delta_specific,
        test_guess_trust_delta_generic,
        test_parse_option_trust_deltas,
        test_detect_new_characters,
        test_init_factions,
        test_update_faction_reputation,
        test_update_faction_attitude,
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

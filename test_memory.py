"""
test_memory.py — 角色记忆系统测试
===============================
测试 memory 模块的核心功能：
  • 角色自动注册
  • 信任度更新
  • metric_history 追踪
  • 势力系统
  • 角色层级管理
"""
import sys
import json
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine.memory import (
    load_memory, save_memory, update_trust,
    set_flag, get_context_for_prompt,
    parse_option_trust_deltas, parse_option_metric_deltas,
    detect_new_characters_from_story,
    get_initial_trust,
    init_factions, update_faction_reputation,
    init_faction_attitudes, update_faction_attitude,
    assign_character_tier, degrade_inactive_characters,
)
from engine.memory_updater import _resolve_chosen_option, apply_trust_deltas

# Use a temp memory path so tests don't pollute real data
_ORIG_MEMORY_PATH = config.MEMORY_PATH


def setup_module():
    """Use temp file for memory during tests."""
    config.MEMORY_PATH = Path(tempfile.mktemp(suffix='.json'))


def teardown_module():
    """Restore original path."""
    config.MEMORY_PATH = _ORIG_MEMORY_PATH


def _fresh_memory():
    """Return a fresh empty memory dict."""
    return {"characters": {}, "world_flags": [], "global_trust": 0.5}


# ── Trust update tests ──────────────────────────────────────────────

def test_update_trust_basic():
    """信任度更新基本功能"""
    mem = _fresh_memory()
    mem["characters"]["林夜"] = {"trust": 0.5, "flags": []}
    update_trust(mem, "林夜", 0.1, turn=1)
    assert abs(mem["characters"]["林夜"]["trust"] - 0.6) < 0.01
    print("✅ 信任度更新: PASS")


def test_update_trust_clamped():
    """信任度 clamp 到 [0, 1]"""
    mem = _fresh_memory()
    mem["characters"]["林夜"] = {"trust": 0.95, "flags": []}
    update_trust(mem, "林夜", 0.2, turn=1)
    assert mem["characters"]["林夜"]["trust"] == 1.0
    print("✅ 信任度上限 clamp: PASS")

    mem["characters"]["艾琳"] = {"trust": 0.05, "flags": []}
    update_trust(mem, "艾琳", -0.2, turn=1)
    assert mem["characters"]["艾琳"]["trust"] == 0.0
    print("✅ 信任度下限 clamp: PASS")


def test_metric_history_tracking():
    """metric_history 自动追踪"""
    mem = _fresh_memory()
    mem["characters"]["林夜"] = {"trust": 0.5, "flags": []}
    update_trust(mem, "林夜", 0.1, turn=3)
    update_trust(mem, "林夜", -0.05, turn=5)

    mh = mem["characters"]["林夜"].get("metric_history", {})
    assert "trust" in mh
    assert len(mh["trust"]) == 2
    assert mh["trust"][0] == [3, 0.6]  # [turn, value]
    assert mh["trust"][1] == [5, 0.55]
    print("✅ metric_history 追踪: PASS")


def test_metric_history_generic():
    """通用 metric 追踪（非 trust）"""
    mem = _fresh_memory()
    mem["characters"]["林夜"] = {"trust": 0.5, "flags": []}
    update_trust(mem, "林夜", 0.1, turn=1, metric="好感度")
    update_trust(mem, "林夜", 0.2, turn=2, metric="fear")

    mh = mem["characters"]["林夜"]["metric_history"]
    assert "好感度" in mh
    assert "fear" in mh
    assert "trust" not in mh  # trust not auto-created when metric specified
    print("✅ 通用 metric 追踪: PASS")


# ── Flag tests ──────────────────────────────────────────────────────

def test_set_flag():
    """Flag 设置 + 去重"""
    mem = _fresh_memory()
    mem["characters"]["林夜"] = {"trust": 0.5, "flags": []}
    set_flag(mem, "林夜", "初次相遇")
    set_flag(mem, "林夜", "初次相遇")  # should not duplicate
    assert "初次相遇" in mem["characters"]["林夜"]["flags"]
    assert len(mem["characters"]["林夜"]["flags"]) == 1
    print("✅ Flag 去重: PASS")


# ── Option parsing tests ────────────────────────────────────────────

def test_parse_option_trust_deltas():
    """解析选项中的信任度 delta"""
    opts = [
        "帮助她完成任务（艾琳信任度+10）",
        "保持中立观察",
        "拒绝她的请求（艾琳信任度-5，林夜信任度+3）",
        "什么都不做",
    ]
    deltas = parse_option_trust_deltas(opts)
    assert len(deltas) >= 3  # at least 3 deltas from 3 meaningful options
    print("✅ 选项信任度解析: PASS")


def test_parse_option_metric_deltas():
    """解析选项中的多维关系 delta"""
    opts = [
        "主动搭话 → 可能缓和 | 友好 | 艾琳↑5, 林夜信任度+10",
        "保持沉默 → 无变化 | 冷淡 | 艾琳 affection-3",
    ]
    deltas = parse_option_metric_deltas(opts)
    names = {d[0] for d in deltas}
    metrics = {d[1] for d in deltas}
    assert "艾琳" in names
    assert "trust" in metrics
    assert "affection" in metrics
    print("✅ 选项多维关系解析: PASS")


def test_resolve_chosen_option_by_letter():
    """A/B/C/D 选项索引解析"""
    opts = [
        "帮助艾琳 → 发展 | 友好 | 艾琳↑5",
        "离开",
        "攻击",
        "观望",
    ]
    resolved = _resolve_chosen_option("A", opts)
    assert opts[0] in resolved
    assert _resolve_chosen_option("C", opts)[0] == opts[2]
    print("✅ 选项字母解析: PASS")


def test_apply_trust_deltas_from_choice_letter():
    """通过 A/B/C/D 选择应用关系变化"""
    mem = _fresh_memory()
    mem["characters"]["艾琳"] = {"trust": 0.5, "flags": [], "metric_history": {"trust": [[0, 0.5]]}}
    opts = ["帮助艾琳 → 发展 | 友好 | 艾琳↑10"]
    apply_trust_deltas(mem, story="", choice="A", turn=1, prev_options=opts)
    assert mem["characters"]["艾琳"]["trust"] > 0.5
    print("✅ 字母选择关系更新: PASS")


# ── Character detection tests ───────────────────────────────────────

def test_detect_new_characters():
    """从故事文本检测新角色"""
    story = "林夜走向了陌生的少女。少女自称雪莉，是一位来自远方的旅者。艾琳警惕地看着她。"
    known = {"林夜", "艾琳"}
    newcomers = detect_new_characters_from_story(story, known)
    assert "雪莉" in newcomers
    print(f"✅ 新角色检测: PASS — 发现 {newcomers}")


# ── Faction tests ───────────────────────────────────────────────────

def test_init_factions():
    """势力初始化"""
    mem = _fresh_memory()
    # Mock a minimal world_pack in config
    init_factions(mem)
    assert "factions" in mem
    assert isinstance(mem["factions"], dict)
    print("✅ 势力初始化: PASS")


def test_faction_reputation():
    """势力声望更新"""
    mem = _fresh_memory()
    mem["factions"] = {"银河联邦": {"reputation": 0.5, "type": "government", "goals": [], "resources": [], "influence": 70}}
    update_faction_reputation(mem, "银河联邦", 0.1, turn=1)
    update_faction_reputation(mem, "银河联邦", -0.05, turn=2)

    assert abs(mem["factions"]["银河联邦"]["reputation"] - 0.55) < 0.01
    mh = mem["factions"]["银河联邦"].get("metric_history", {}).get("reputation", [])
    assert len(mh) == 2
    print("✅ 势力声望更新: PASS")


# ── Tier tests ──────────────────────────────────────────────────────

def test_assign_tier():
    """角色层级分配"""
    mem = _fresh_memory()
    mem["characters"]["林夜"] = {"trust": 0.7, "flags": []}
    mem["characters"]["路人甲"] = {"trust": 0.3, "flags": []}

    # Mock world_pack with is_main character
    world_pack = {
        "world": {
            "characters": [
                {"name": "林夜", "is_main": True},
            ]
        }
    }
    assign_character_tier(mem, "林夜", world_pack, is_main=True)
    assign_character_tier(mem, "路人甲", world_pack)

    assert mem["characters"]["林夜"]["tier"] == "主角"
    assert mem["characters"]["路人甲"]["tier"] in ("背景", "重要")
    print("✅ 角色层级分配: PASS")


def test_degrade_inactive():
    """非活跃角色降级"""
    mem = _fresh_memory()
    mem["characters"]["路人甲"] = {
        "trust": 0.3, "flags": [], "tier": "重要",
        "last_appearance_turn": 1,
    }
    degrade_inactive_characters(mem, current_turn=20)
    # After 19 turns of inactivity, should degrade
    assert mem["characters"]["路人甲"]["tier"] in ("背景", "退休")
    print("✅ 非活跃角色降级: PASS")


# ── Context generation ──────────────────────────────────────────────

def test_get_context_for_prompt():
    """为 prompt 生成角色上下文"""
    mem = {
        "characters": {
            "林夜": {"trust": 0.7, "flags": ["初次相遇"], "relationship": "船长"},
            "艾琳": {"trust": 0.5, "flags": [], "relationship": "同事"},
        },
        "world_flags": [],
    }
    ctx = get_context_for_prompt(mem)
    assert "林夜" in ctx
    assert "艾琳" in ctx
    print("✅ Prompt 上下文生成: PASS")


if __name__ == "__main__":
    setup_module()
    tests = [
        test_update_trust_basic, test_update_trust_clamped,
        test_metric_history_tracking, test_metric_history_generic,
        test_set_flag, test_parse_option_trust_deltas,
        test_parse_option_metric_deltas, test_resolve_chosen_option_by_letter,
        test_apply_trust_deltas_from_choice_letter,
        test_detect_new_characters, test_init_factions,
        test_faction_reputation, test_assign_tier,
        test_degrade_inactive, test_get_context_for_prompt,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ FAIL: {test.__name__} — {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    teardown_module()
    print(f"\n{'🎉' if failed == 0 else '❌'} Memory tests: {len(tests) - failed}/{len(tests)} passed, {failed} failed")
    sys.exit(1 if failed else 0)

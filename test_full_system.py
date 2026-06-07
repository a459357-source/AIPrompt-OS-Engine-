"""
test_full_system.py — 全系统集成测试
===================================
端到端测试：状态机 → 图谱 → 记忆 → 存档 → API 的完整链路。
不调用真实 AI API（使用 mock），测试所有子系统协作。

运行: python prompt-os-engine/test_full_system.py
"""
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine import io_utils
from engine.state_manager import apply_turn
from engine.router import load_graph, save_graph, append_node, get_leaf_count
from engine.memory import (
    load_memory, save_memory, update_trust,
    get_context_for_prompt, get_char_stats_for_ui,
)
from engine.analytics import compute_all, metrics_curves, summary_stats
from engine.io_utils import append_markdown

# Save original paths
_ORIG_PATHS = {}


def setup_module():
    """Isolate all data files to temp directory."""
    tmp = Path(tempfile.mkdtemp())
    _ORIG_PATHS.update({
        'state': config.SESSION_STATE_PATH,
        'graph': config.STORY_GRAPH_PATH,
        'memory': config.MEMORY_PATH,
        'chapter': config.CHAPTER_PATH,
        'saves': config.SAVES_DIR,
        'api_usage': config.API_USAGE_PATH,
    })

    config.SESSION_STATE_PATH = tmp / "state.yaml"
    config.STORY_GRAPH_PATH = tmp / "graph.json"
    config.MEMORY_PATH = tmp / "memory.json"
    config.CHAPTER_PATH = tmp / "chapter.md"
    config.SAVES_DIR = tmp / "saves"
    config.API_USAGE_PATH = tmp / "api_usage.jsonl"

    # Initialize with a fresh game world
    io_utils.write_yaml(config.SESSION_STATE_PATH, {
        "scene": "星门基地 — 主控室",
        "status": "SETUP",
        "turn": 0,
        "characters": {
            "A": {"name": "林夜", "role": "舰长", "level": "L0", "relation": "初识"},
            "B": {"name": "艾琳", "role": "考古学家", "level": "L0", "relation": "初识"},
        },
        "history": [],
        "chapter": 1,
        "force_event_pending": False,
    })
    io_utils.write_json(config.STORY_GRAPH_PATH, {
        "nodes": {"0": {"turn": 0, "text": "初始：星门基地主控室", "scene": "星门基地 — 主控室",
                        "status": "SETUP", "choices": {}, "parent": None, "choice_taken": None}},
        "current_node": "0",
        "edges": [],
    })
    io_utils.write_json(config.MEMORY_PATH, {
        "characters": {
            "林夜": {"trust": 0.5, "flags": [], "relationship": "舰长，初识"},
            "艾琳": {"trust": 0.5, "flags": [], "relationship": "考古学家，初识"},
        },
        "world_flags": [],
        "global_trust": 0.5,
    })


def teardown_module():
    for key, path in _ORIG_PATHS.items():
        setattr(config, {
            'state': 'SESSION_STATE_PATH',
            'graph': 'STORY_GRAPH_PATH',
            'memory': 'MEMORY_PATH',
            'chapter': 'CHAPTER_PATH',
            'saves': 'SAVES_DIR',
            'api_usage': 'API_USAGE_PATH',
        }[key], path)


# ── Mock AI response factory ────────────────────────────────────────

def _mock_ai_response(turn: int, status: str = "BUILD", scene: str = "星门基地 — 舰桥",
                      story: str = "", options: list[str] | None = None):
    """Build a realistic DeepSeek response dict for testing."""
    if not story:
        story = (
            f"第{turn}轮：林夜站在舰桥中央，凝视着全息投影上的星图。"
            f"艾琳从身后走来，手中拿着一份刚刚解密的数据晶片。"
            f"「舰长，我们在第三象限探测到了异常能量信号。」"
            f"她的声音里带着一丝兴奋。"
            f"林夜转过身，点了点头。「准备跃迁。」"
        )
    if options is None:
        options = [
            "立即跃迁调查信号源（艾琳好感度+5）",
            "先收集更多数据再做决定",
            "派遣探测器先行侦察",
            "与星门基地指挥部取得联系",
        ]
    return {
        "story": story,
        "state": {
            "status": status,
            "scene": scene,
            "characters": {
                "A": {"name": "林夜", "level": f"L{min(turn, 4)}"},
                "B": {"name": "艾琳", "level": f"L{min(turn, 4)}"},
            },
        },
        "options": options,
    }


# ── Integration tests ───────────────────────────────────────────────

def test_state_machine_integration():
    """状态机：多轮推进，验证状态流转"""
    for turn_num in range(1, 6):
        response = _mock_ai_response(turn_num)
        new_state = apply_turn(response, choice="A")

        assert new_state["turn"] == turn_num
        assert len(new_state["history"]) == turn_num

        # Status should advance over time
        if turn_num >= 4:
            assert new_state["status"] in ("TENSION", "CLIMAX", "COOLDOWN", "BUILD")

    print("✅ 状态机多轮流转: PASS")


def test_graph_integration():
    """图谱：多轮追加 + 分支 + 统计"""
    graph = load_graph()

    for i in range(1, 6):
        choice = "A" if i % 2 == 1 else "B"
        nid = append_node(
            graph,
            parent_node=str(i - 1),
            choice_taken=choice,
            turn=i,
            story_snippet=f"第{i}轮故事片段",
            scene="测试场景",
            status="BUILD" if i < 3 else "TENSION",
            options=["A", "B", "C", "D"],
        )
        assert nid == str(i)

    save_graph(graph)
    assert len(graph["nodes"]) == 6  # 0-5
    assert len(graph["edges"]) == 5
    assert get_leaf_count(graph) == 1  # only node 5 has no outgoing edges

    print("✅ 图谱多轮追加: PASS")


def test_memory_integration():
    """记忆系统：信任度更新 + metric_history"""
    memory = load_memory()

    # Simulate 5 turns of trust updates
    for t in range(1, 6):
        update_trust(memory, "林夜", 0.05, t)
        update_trust(memory, "艾琳", 0.03 if t % 2 == 0 else -0.02, t)

    save_memory(memory)

    mem2 = load_memory()
    lin_trust = mem2["characters"]["林夜"]["trust"]
    assert lin_trust > 0.5  # should have increased
    assert lin_trust <= 1.0

    # metric_history should have 5 entries
    mh = mem2["characters"]["林夜"].get("metric_history", {}).get("trust", [])
    assert len(mh) == 5

    print(f"✅ 记忆更新: PASS — 林夜信任度 {lin_trust:.2f}")


def test_chapter_writing():
    """章节写入：frontmatter 只在首轮写入"""
    # Clear chapter
    config.CHAPTER_PATH.write_text("", encoding="utf-8")

    for t in range(1, 4):
        append_markdown(
            config.CHAPTER_PATH,
            f"# Chapter {t}\n\n故事内容第{t}轮\n",
            {"turn": t, "status": "BUILD", "scene": "测试"},
        )

    content = config.CHAPTER_PATH.read_text(encoding="utf-8")
    # Count YAML frontmatter blocks (--- at start of line)
    fm_count = content.count("\n---\n")
    # Should only have 1 opening ---...--- block (counts as 2 --- appearances)
    assert fm_count <= 2, f"Expected ≤2 '---' separators, got {fm_count}"
    print(f"✅ 章节 Frontmatter: PASS — {fm_count} separators")


def test_analytics_computation():
    """分析引擎：数据计算"""
    analytics = compute_all()

    assert "summary" in analytics
    assert "metrics_curves" in analytics
    assert "status_timeline" in analytics
    assert "branch_stats" in analytics

    summary = analytics["summary"]
    assert summary["turns"] >= 5
    assert summary["nodes"] >= 6

    print(f"✅ 分析引擎: PASS — {summary['nodes']} nodes, {summary['turns']} turns")


def test_char_stats_for_ui():
    """UI 角色统计"""
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    memory = load_memory()
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)

    stats = get_char_stats_for_ui(state, memory, world_pack)
    assert isinstance(stats, list)
    print(f"✅ UI 角色统计: PASS — {len(stats)} characters")


def test_downsample_history():
    """下采样：超限数据截断"""
    from engine.analytics import _downsample_history

    # Create 200-point history
    history = [[i, 0.5] for i in range(200)]
    result = _downsample_history(history, max_points=50)
    assert len(result) <= 50
    # Should keep recent points
    assert result[-1][0] == 199  # last point preserved
    print(f"✅ 下采样: PASS — {len(history)} → {len(result)} points")


def test_safe_call():
    """_safe_call 异常不崩溃"""
    from engine.run import _safe_call

    def _will_raise():
        raise ValueError("test error")

    result = _safe_call(_will_raise, "test label")
    assert result is False  # should return False, not raise

    def _ok():
        return 42

    result = _safe_call(_ok, "test ok")
    assert result is True
    print("✅ _safe_call: PASS")


def test_prev_options_from_history():
    """_get_prev_options 从历史读取"""
    from engine.run import _get_prev_options

    state = {
        "history": [
            {"options": ["A1", "B1", "C1", "D1"]},
            {"options": ["A2", "B2", "C2", "D2"]},
        ]
    }
    opts = _get_prev_options(state)
    assert opts == ["A1", "B1", "C1", "D1"]

    # Single entry → empty
    state2 = {"history": [{"options": ["A1"]}]}
    assert _get_prev_options(state2) == []

    # Empty → empty
    assert _get_prev_options({}) == []
    print("✅ _get_prev_options: PASS")


if __name__ == "__main__":
    setup_module()
    tests = [
        test_state_machine_integration,
        test_graph_integration,
        test_memory_integration,
        test_chapter_writing,
        test_analytics_computation,
        test_char_stats_for_ui,
        test_downsample_history,
        test_safe_call,
        test_prev_options_from_history,
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
    print(f"\n{'🎉' if failed == 0 else '❌'} Full system tests: {len(tests) - failed}/{len(tests)} passed, {failed} failed")
    sys.exit(1 if failed else 0)

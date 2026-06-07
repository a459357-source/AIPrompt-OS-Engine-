"""
test_graph.py — 剧情图谱系统测试
===============================
测试 router 模块的核心功能：
  • 节点添加
  • 分支路由
  • 路径遍历
  • 叶子节点统计
"""
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine.router import (
    load_graph, save_graph, get_current_node,
    append_node, route, get_path_to_root, get_leaf_count,
)

_ORIG_GRAPH_PATH = config.STORY_GRAPH_PATH


def setup_module():
    config.STORY_GRAPH_PATH = Path(tempfile.mktemp(suffix='.json'))


def teardown_module():
    config.STORY_GRAPH_PATH = _ORIG_GRAPH_PATH


def _fresh_graph():
    return {
        "nodes": {
            "0": {
                "turn": 0, "text": "初始场景",
                "scene": "舰桥", "status": "SETUP",
                "choices": {}, "parent": None, "choice_taken": None,
            }
        },
        "current_node": "0",
        "edges": [],
    }


def test_append_node():
    """添加剧情节点"""
    g = _fresh_graph()
    nid = append_node(g, "0", "A", 1, "故事内容...", "机库", "BUILD",
                      ["选项A", "选项B", "选项C", "选项D"])
    assert nid == "1"
    assert "1" in g["nodes"]
    assert g["nodes"]["1"]["turn"] == 1
    assert g["nodes"]["1"]["scene"] == "机库"
    assert g["current_node"] == "1"
    # Edge should exist
    assert len(g["edges"]) == 1
    assert g["edges"][0]["from"] == "0"
    assert g["edges"][0]["to"] == "1"
    assert g["edges"][0]["choice"] == "A"
    print("✅ 节点添加: PASS")


def test_append_multiple_nodes():
    """多节点追加 + 分支"""
    g = _fresh_graph()
    append_node(g, "0", "A", 1, "分支A", "地点A", "BUILD",
                ["选1", "选2", "选3", "选4"])
    append_node(g, "0", "B", 1, "分支B", "地点B", "BUILD",
                ["选1", "选2", "选3", "选4"])
    append_node(g, "1", "A", 2, "继续A", "地点C", "TENSION",
                ["选1", "选2", "选3", "选4"])

    assert len(g["nodes"]) == 4  # 0, 1, 2, 3
    assert len(g["edges"]) == 3
    assert g["current_node"] == "3"
    print("✅ 多节点分支: PASS")


def test_route():
    """路由跟随"""
    g = _fresh_graph()
    append_node(g, "0", "A", 1, "分支A", "地点A", "BUILD",
                ["选1", "选2", "选3", "选4"])
    dest = route("0", "A", g)
    assert dest == "1"
    dest_none = route("0", "C", g)
    assert dest_none is None
    print("✅ 路由跟随: PASS")


def test_get_path_to_root():
    """获取根路径"""
    g = _fresh_graph()
    append_node(g, "0", "A", 1, "第1轮", "S1", "BUILD",
                ["a", "b", "c", "d"])
    append_node(g, "1", "B", 2, "第2轮", "S2", "TENSION",
                ["a", "b", "c", "d"])

    path = get_path_to_root(g, "2")
    assert len(path) == 3  # 0 → 1 → 2
    assert path[0]["id"] == "0"
    assert path[1]["id"] == "1"
    assert path[2]["id"] == "2"
    print("✅ 根路径遍历: PASS")


def test_leaf_count():
    """叶子节点统计"""
    g = _fresh_graph()
    # 0 has A→1, B→2; 1 has A→3; so leaves are 2 and 3
    append_node(g, "0", "A", 1, "分支A", "SA", "BUILD",
                ["a", "b", "c", "d"])
    append_node(g, "0", "B", 1, "分支B", "SB", "BUILD",
                ["a", "b", "c", "d"])
    append_node(g, "1", "A", 2, "续A", "SC", "TENSION",
                ["a", "b", "c", "d"])

    leaves = get_leaf_count(g)
    assert leaves == 2  # nodes 2 and 3 are leaves
    print(f"✅ 叶子节点统计: PASS — {leaves} leaves")


def test_save_load_roundtrip():
    """图谱持久化往返"""
    g = _fresh_graph()
    append_node(g, "0", "A", 1, "test", "S", "BUILD",
                ["a", "b", "c", "d"])
    save_graph(g)
    g2 = load_graph()
    assert len(g2["nodes"]) == 2
    assert g2["nodes"]["1"]["scene"] == "S"
    print("✅ 图谱持久化: PASS")


if __name__ == "__main__":
    setup_module()
    tests = [
        test_append_node, test_append_multiple_nodes,
        test_route, test_get_path_to_root,
        test_leaf_count, test_save_load_roundtrip,
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
    print(f"\n{'🎉' if failed == 0 else '❌'} Graph tests: {len(tests) - failed}/{len(tests)} passed, {failed} failed")
    sys.exit(1 if failed else 0)

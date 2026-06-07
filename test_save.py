"""
test_save.py — 存档系统测试
===========================
测试 save_manager 模块：
  • 存档 / 读档
  • 存档列表
  • autosave
  • 存档槽上限
"""
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine import io_utils
from engine import save_manager

_ORIG_SAVES_DIR = config.SAVES_DIR
_ORIG_STATE_PATH = config.SESSION_STATE_PATH
_ORIG_GRAPH_PATH = config.STORY_GRAPH_PATH
_ORIG_MEMORY_PATH = config.MEMORY_PATH


def setup_module():
    """Use temp files for all data during save tests."""
    tmp = Path(tempfile.mkdtemp())
    config.SAVES_DIR = tmp / "saves"
    config.SESSION_STATE_PATH = tmp / "state.yaml"
    config.STORY_GRAPH_PATH = tmp / "graph.json"
    config.MEMORY_PATH = tmp / "memory.json"

    # Create minimal state
    io_utils.write_yaml(config.SESSION_STATE_PATH, {
        "scene": "测试场景", "status": "SETUP", "turn": 5,
        "characters": {"A": {"name": "测试角色", "level": "L1"}},
        "history": [{"turn": 1, "story": "测试故事", "options": ["A", "B", "C", "D"]}],
    })
    io_utils.write_json(config.STORY_GRAPH_PATH, {
        "nodes": {"0": {"turn": 0, "text": "init"}}, "current_node": "0", "edges": [],
    })
    io_utils.write_json(config.MEMORY_PATH, {
        "characters": {"测试角色": {"trust": 0.6}}, "world_flags": [],
    })


def teardown_module():
    config.SAVES_DIR = _ORIG_SAVES_DIR
    config.SESSION_STATE_PATH = _ORIG_STATE_PATH
    config.STORY_GRAPH_PATH = _ORIG_GRAPH_PATH
    config.MEMORY_PATH = _ORIG_MEMORY_PATH


def test_save_and_load():
    """存档→读档往返"""
    # Save to slot1
    result = save_manager.save("slot1")
    assert result is not None, "save() returned None"
    assert result["turn"] == 5
    print("✅ 存档: PASS")

    # Verify slot exists
    assert save_manager.save_exists("slot1")
    print("✅ 存档槽存在: PASS")

    # Load
    success = save_manager.load("slot1")
    assert success is not None, "load() returned None"
    # State should be restored
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    assert state.get("turn") == 5
    print("✅ 读档恢复: PASS")


def test_autosave():
    """自动存档"""
    result = save_manager.autosave()
    assert result is not None
    assert save_manager.save_exists("autosave")
    print("✅ 自动存档: PASS")


def test_list_saves():
    """存档列表"""
    save_manager.save("slot1")
    save_manager.save("slot2")
    saves = save_manager.list_saves()
    assert len(saves) >= 2
    print(f"✅ 存档列表: PASS — {len(saves)} slots")


def test_save_nonexistent_load():
    """加载不存在的存档返回 None"""
    result = save_manager.load("nonexistent_slot")
    assert result is None
    print("✅ 不存在存档加载: PASS")


if __name__ == "__main__":
    setup_module()
    tests = [test_save_and_load, test_autosave, test_list_saves, test_save_nonexistent_load]
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
    print(f"\n{'🎉' if failed == 0 else '❌'} Save tests: {len(tests) - failed}/{len(tests)} passed, {failed} failed")
    sys.exit(1 if failed else 0)

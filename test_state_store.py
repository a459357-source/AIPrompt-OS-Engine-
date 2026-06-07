"""
test_state_store.py — RuntimeState load/commit tests
"""
import json
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine import io_utils
from engine.state_store import RuntimeState, load_runtime, commit_runtime, commit_bundle

_ORIG_STATE = config.SESSION_STATE_PATH
_ORIG_MEMORY = config.MEMORY_PATH
_ORIG_GRAPH = config.STORY_GRAPH_PATH
_ORIG_CHAPTER = config.CHAPTER_PATH
_ORIG_DATA = config.DATA_DIR


def setup_module():
    tmp = Path(tempfile.mkdtemp())
    config.DATA_DIR = tmp / "data"
    config.SESSION_STATE_PATH = tmp / "session_state.yaml"
    config.MEMORY_PATH = config.DATA_DIR / "memory.json"
    config.STORY_GRAPH_PATH = config.DATA_DIR / "story_graph.json"
    config.CHAPTER_PATH = tmp / "output" / "chapter.md"

    commit_bundle(
        {"turn": 1, "scene": "A", "status": "SETUP", "history": []},
        {"characters": {"测试": {"trust": 0.5}}, "world_flags": []},
        {"nodes": {"0": {"turn": 0}}, "current_node": "0", "edges": []},
        chapter="# Chapter 1\n",
    )


def teardown_module():
    config.SESSION_STATE_PATH = _ORIG_STATE
    config.MEMORY_PATH = _ORIG_MEMORY
    config.STORY_GRAPH_PATH = _ORIG_GRAPH
    config.CHAPTER_PATH = _ORIG_CHAPTER
    config.DATA_DIR = _ORIG_DATA


def test_load_commit_roundtrip():
    rt = load_runtime()
    assert rt.session.get("turn") == 1
    assert "测试" in rt.memory.get("characters", {})
    assert rt.chapter.startswith("# Chapter")

    rt.session["turn"] = 2
    rt.memory["characters"]["测试"]["trust"] = 0.8
    rt.graph["edges"] = [{"from": "0", "to": "1", "choice": "A"}]
    commit_runtime(rt)

    rt2 = load_runtime(clear_cache=True)
    assert rt2.session["turn"] == 2
    assert rt2.memory["characters"]["测试"]["trust"] == 0.8
    assert len(rt2.graph["edges"]) == 1
    print("✅ load/commit 往返: PASS")


def test_atomic_commit_preserves_on_bad_data(monkeypatch):
    original = io_utils.read_yaml(config.SESSION_STATE_PATH)
    rt = load_runtime()
    rt.session["turn"] = 99

    def _fail_replace(*_args, **_kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("engine.state_store.os.replace", _fail_replace)
    try:
        commit_runtime(rt)
        assert False, "should have raised"
    except OSError:
        restored = io_utils.read_yaml(config.SESSION_STATE_PATH)
        assert restored.get("turn") == original.get("turn")
    print("✅ 失败回滚保留原文件: PASS")


def test_commit_bundle_chapter():
    commit_bundle(
        {"turn": 3, "scene": "B", "status": "BUILD", "history": []},
        {"characters": {}, "world_flags": []},
        {"nodes": {}, "current_node": "0", "edges": []},
        chapter="new chapter text",
    )
    assert config.CHAPTER_PATH.read_text(encoding="utf-8") == "new chapter text"
    print("✅ chapter 原子写入: PASS")


if __name__ == "__main__":
    setup_module()
    tests = [test_load_commit_roundtrip, test_atomic_commit_preserves_on_bad_data, test_commit_bundle_chapter]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ FAIL: {t.__name__} — {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    teardown_module()
    print(f"\n{'🎉' if failed == 0 else '❌'} state_store: {len(tests) - failed}/{len(tests)} passed")

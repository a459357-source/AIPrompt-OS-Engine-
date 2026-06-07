"""
test_api.py — Web API 端点测试
==============================
使用 FastAPI TestClient 测试所有关键端点：
  • 健康检查
  • 游戏状态读取（GET，无副作用）
  • 仪表盘数据
  • NPC 列表
  • 历史记录
  • 存档操作
"""
import sys
import tempfile
from pathlib import Path

import config

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine import io_utils

# Isolate test data
_ORIG_PATHS = {}


def setup_module():
    """Use temp files for all state during API tests."""
    tmp = Path(tempfile.mkdtemp())
    _ORIG_PATHS['state'] = config.SESSION_STATE_PATH
    _ORIG_PATHS['graph'] = config.STORY_GRAPH_PATH
    _ORIG_PATHS['memory'] = config.MEMORY_PATH
    _ORIG_PATHS['saves'] = config.SAVES_DIR
    _ORIG_PATHS['chapter'] = config.CHAPTER_PATH

    config.SESSION_STATE_PATH = tmp / "state.yaml"
    config.STORY_GRAPH_PATH = tmp / "graph.json"
    config.MEMORY_PATH = tmp / "memory.json"
    config.SAVES_DIR = tmp / "saves"
    config.CHAPTER_PATH = tmp / "chapter.md"

    # Minimal initial state (no history → triggers not_started on GET /api/game-state)
    io_utils.write_yaml(config.SESSION_STATE_PATH, {
        "scene": "测试舰桥", "status": "SETUP", "turn": 0,
        "characters": {
            "A": {"name": "林夜", "role": "船长", "level": "L0", "relation": "初识"},
        },
        "history": [],
        "chapter": 1,
    })
    io_utils.write_json(config.STORY_GRAPH_PATH, {
        "nodes": {"0": {"turn": 0, "text": "init"}}, "current_node": "0", "edges": [],
    })
    io_utils.write_json(config.MEMORY_PATH, {
        "characters": {"林夜": {"trust": 0.5, "flags": []}}, "world_flags": [],
    })


def teardown_module():
    for key, path in _ORIG_PATHS.items():
        if key == 'state':
            config.SESSION_STATE_PATH = path
        elif key == 'graph':
            config.STORY_GRAPH_PATH = path
        elif key == 'memory':
            config.MEMORY_PATH = path
        elif key == 'saves':
            config.SAVES_DIR = path
        elif key == 'chapter':
            config.CHAPTER_PATH = path


def test_health_endpoint():
    """健康检查端点"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    print("✅ 健康检查: PASS")


def test_game_state_readonly():
    """GET /api/game-state 只读（无副作用）"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/api/game-state")
    assert resp.status_code == 200
    data = resp.json()
    # No history → should return not_started=True
    assert data.get("not_started") is True
    assert data["state"]["turn"] == 0
    print("✅ game-state 只读: PASS")


def test_world_meta_endpoint():
    """GET /api/world-meta 返回 world_pack 标题"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/api/world-meta")
    assert resp.status_code == 200
    data = resp.json()
    assert "world_title" in data
    assert isinstance(data["world_title"], str)
    print("✅ world-meta 端点: PASS")


def test_dashboard_endpoint():
    """仪表盘数据端点"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "turn" in data
    assert "analytics" in data  # should include analytics now
    assert "plot_director" in data
    assert "main_plot" in data["plot_director"]
    print("✅ 仪表盘端点: PASS")


def test_npcs_endpoint():
    """NPC 列表端点"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/api/npcs")
    assert resp.status_code == 200
    data = resp.json()
    assert "characters" in data
    assert "stats" in data
    print("✅ NPC 列表: PASS")


def test_history_endpoint():
    """历史记录端点"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/api/history")
    assert resp.status_code == 200
    data = resp.json()
    assert "turns" in data
    print("✅ 历史记录: PASS")


def test_start_is_idempotent(monkeypatch):
    """POST /api/start must not regenerate when history already exists."""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    io_utils.write_yaml(config.SESSION_STATE_PATH, {
        "scene": "舰桥", "status": "BUILD", "turn": 1,
        "characters": {},
        "history": [{
            "turn": 1,
            "story": "已有正文",
            "options": ["A", "B", "C", "D"],
            "choice": None,
        }],
        "chapter": 1,
    })

    called = {"step": 0}

    def _fake_step(*_args, **_kwargs):
        called["step"] += 1
        return {"story": "不应生成", "options": [], "state": {}}

    monkeypatch.setattr("engine.run.step", _fake_step)

    client = TestClient(app)
    resp = client.post("/api/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["story"] == "已有正文"
    assert called["step"] == 0
    print("✅ /api/start 幂等: PASS")


def test_next_is_post_only():
    """POST /api/next 接受 POST，拒绝 GET（因为已改为 POST-only）"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    # GET should 405 (Method Not Allowed) now
    resp = client.get("/api/next?choice=A")
    assert resp.status_code in (404, 405, 422)
    print("✅ /api/next POST-only: PASS")


def test_game_settings_post():
    """POST /api/game-settings saves generation quick settings."""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.post("/api/game-settings", data={"story_length": "4000"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert data.get("story_length") == 4000
    assert data.get("max_tokens") == config.tokens_for_story_length(4000)

    resp_slash = client.post("/api/game-settings/", data={"story_length": "3000"})
    assert resp_slash.status_code == 200
    assert resp_slash.json().get("story_length") == 3000
    print("✅ game-settings POST: PASS")


def test_saves_endpoints():
    """存档端点"""
    from ui.web_app import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    # List saves
    resp = client.get("/saves")
    assert resp.status_code == 200
    print("✅ 存档列表: PASS")

    # Save to slot1
    resp = client.get("/save?slot=slot1")
    assert resp.status_code == 200
    print("✅ 存档: PASS")


if __name__ == "__main__":
    setup_module()
    tests = [
        test_health_endpoint, test_game_state_readonly,
        test_dashboard_endpoint, test_npcs_endpoint,
        test_history_endpoint, test_start_is_idempotent, test_next_is_post_only,
        test_game_settings_post,
        test_saves_endpoints,
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
    print(f"\n{'🎉' if failed == 0 else '❌'} API tests: {len(tests) - failed}/{len(tests)} passed, {failed} failed")
    sys.exit(1 if failed else 0)

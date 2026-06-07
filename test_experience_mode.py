"""Tests for ADR-001 experience_mode compatibility layer."""
import json

import pytest

import config
from engine.adult_unlock import generate_unlock_key, write_secret
from engine.save_manager import load, save


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    secret_path = tmp_path / "adult_unlock_secret"
    settings_path = tmp_path / "apikey.json"
    saves_dir = tmp_path / "saves"
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "APIKEY_PATH", settings_path)
    monkeypatch.setattr(config, "SAVES_DIR", saves_dir)
    write_secret()
    return {"settings_path": settings_path, "saves_dir": saves_dir}


def test_normalize_experience_mode():
    assert config.normalize_experience_mode("story") == "story"
    assert config.normalize_experience_mode("adult") == "adult"
    assert config.normalize_experience_mode("invalid") == config.DEFAULT_EXPERIENCE_MODE


def test_mode_adult_mapping():
    assert config.experience_mode_to_adult_mode("story") is False
    assert config.experience_mode_to_adult_mode("adult") is True
    assert config.adult_mode_to_experience_mode(True) == "adult"
    assert config.adult_mode_to_experience_mode(False) == "story"


def test_legacy_adult_mode_fallback(settings_env, monkeypatch):
    monkeypatch.delenv("PROMPTOS_SKIP_ADULT_UNLOCK", raising=False)
    key = generate_unlock_key()
    config.save_adult_unlock_key(key)
    config._update_settings(adult_mode=True)
    config.reload_experience_mode()
    assert config.get_experience_mode() == "adult"
    assert config.ADULT_MODE is True


def test_save_experience_mode_dual_writes(settings_env, monkeypatch):
    monkeypatch.delenv("PROMPTOS_SKIP_ADULT_UNLOCK", raising=False)
    key = generate_unlock_key()
    config.save_adult_unlock_key(key)
    config.save_experience_mode("adult")
    config.reload_app_behavior()
    raw = json.loads(settings_env["settings_path"].read_text(encoding="utf-8"))
    assert raw["experience_mode"] == "adult"
    assert raw["adult_mode"] is True


def test_save_adult_mode_dual_writes_experience_mode(settings_env, monkeypatch):
    monkeypatch.delenv("PROMPTOS_SKIP_ADULT_UNLOCK", raising=False)
    key = generate_unlock_key()
    config.save_adult_unlock_key(key)
    config.save_adult_mode(True)
    config.reload_app_behavior()
    assert config.get_experience_mode() == "adult"
    raw = json.loads(settings_env["settings_path"].read_text(encoding="utf-8"))
    assert raw["experience_mode"] == "adult"


def test_experience_mode_requires_unlock(settings_env, monkeypatch):
    monkeypatch.delenv("PROMPTOS_SKIP_ADULT_UNLOCK", raising=False)
    with pytest.raises(ValueError, match="解锁密钥"):
        config.save_experience_mode("adult")


def test_save_snapshot_prefers_experience_mode(settings_env, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(config, "STORY_GRAPH_PATH", tmp_path / "story_graph.json")
    monkeypatch.setattr(config, "CHAPTER_PATH", tmp_path / "chapter.md")
    monkeypatch.setattr(config, "PLOT_STATE_PATH", tmp_path / "plot_state.json")
    monkeypatch.setattr(config, "CANDIDATE_NPCS_PATH", tmp_path / "candidate_npcs.json")
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")

    import yaml
    from engine import io_utils

    io_utils.write_yaml(config.SESSION_STATE_PATH, {"turn": 1, "status": "SETUP"})
    io_utils.write_json(config.MEMORY_PATH, {})
    io_utils.write_json(config.STORY_GRAPH_PATH, {"nodes": {}, "edges": []})
    io_utils.write_json(config.PLOT_STATE_PATH, {"main_plot": {"progress": 0}})
    io_utils.write_yaml(config.WORLD_PACK_PATH, {"world": {}})

    monkeypatch.setenv("PROMPTOS_SKIP_ADULT_UNLOCK", "1")
    config.save_experience_mode("adult")
    config.reload_app_behavior()
    save("slot1")

    config.save_experience_mode("story")
    config.reload_app_behavior()
    load("slot1")
    config.reload_app_behavior()
    assert config.get_experience_mode() == "adult"


def test_legacy_snapshot_adult_mode_fallback(settings_env, monkeypatch, tmp_path):
    slot_path = settings_env["saves_dir"] / "slot1.json"
    settings_env["saves_dir"].mkdir(parents=True, exist_ok=True)
    snapshot = {
        "version": "2.0.0",
        "slot": "slot1",
        "session_state": {"turn": 0},
        "memory": {},
        "story_graph": {"nodes": {}, "edges": []},
        "adult_mode": True,
    }
    slot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(config, "STORY_GRAPH_PATH", tmp_path / "story_graph.json")
    monkeypatch.setattr(config, "CHAPTER_PATH", tmp_path / "chapter.md")
    monkeypatch.setattr(config, "PLOT_STATE_PATH", tmp_path / "plot_state.json")
    monkeypatch.setattr(config, "CANDIDATE_NPCS_PATH", tmp_path / "candidate_npcs.json")
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")

    from engine import io_utils

    io_utils.write_yaml(config.WORLD_PACK_PATH, {"world": {}})

    monkeypatch.setenv("PROMPTOS_SKIP_ADULT_UNLOCK", "1")
    config.save_experience_mode("story")
    config.reload_app_behavior()
    load("slot1")
    config.reload_app_behavior()
    assert config.get_experience_mode() == "adult"

"""Frozen-bundle path resolution (PyInstaller _MEIPASS)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import config


@pytest.fixture
def bundle_layout(tmp_path: Path, monkeypatch):
    """Simulate PromptOS.exe + _internal/ bundle layout."""
    exe_dir = tmp_path / "PromptOS"
    internal = exe_dir / "_internal"
    internal.mkdir(parents=True)
    (internal / "engine.yaml").write_text("engine: test\n", encoding="utf-8")
    (internal / "prompt_template.yaml").write_text("template: test\n", encoding="utf-8")
    defaults = internal / "packaging" / "defaults"
    defaults.mkdir(parents=True)
    (defaults / "apikey.json").write_text("{}", encoding="utf-8")
    (defaults / "memory.json").write_text("{}", encoding="utf-8")
    (defaults / "story_graph.json").write_text("{}", encoding="utf-8")
    (defaults / "session_state.yaml").write_text("turn: 0\n", encoding="utf-8")
    (defaults / "world_pack.yaml").write_text("world: test\n", encoding="utf-8")
    dist = internal / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")

    fake_exe = exe_dir / "PromptOS.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    monkeypatch.setattr(sys, "_MEIPASS", str(internal), raising=False)

    monkeypatch.setattr(config, "ROOT", exe_dir)
    monkeypatch.setattr(config, "BUNDLE_ROOT", internal)
    monkeypatch.setattr(config, "DATA_DIR", exe_dir / "data")
    monkeypatch.setattr(config, "OUTPUT_DIR", exe_dir / "output")
    monkeypatch.setattr(config, "SAVES_DIR", exe_dir / "data" / "saves")
    monkeypatch.setattr(config, "APIKEY_PATH", exe_dir / "data" / "apikey.json")
    monkeypatch.setattr(config, "MEMORY_PATH", exe_dir / "data" / "memory.json")
    monkeypatch.setattr(config, "STORY_GRAPH_PATH", exe_dir / "data" / "story_graph.json")
    monkeypatch.setattr(config, "SESSION_STATE_PATH", exe_dir / "session_state.yaml")
    monkeypatch.setattr(config, "WORLD_PACK_PATH", exe_dir / "world_pack.yaml")
    monkeypatch.setattr(
        config,
        "ENGINE_CONFIG_PATH",
        config.bundled_asset("engine.yaml"),
    )
    monkeypatch.setattr(
        config,
        "PROMPT_TEMPLATE_PATH",
        config.bundled_asset("prompt_template.yaml"),
    )
    monkeypatch.setattr(
        config,
        "FRONTEND_DIST",
        config.bundle_path("frontend", "dist"),
    )
    monkeypatch.setattr(
        config,
        "BUNDLE_DEFAULTS_DIR",
        config.bundle_path("packaging", "defaults"),
    )
    return exe_dir, internal


def test_bundled_assets_resolve_to_meipass(bundle_layout):
    _, internal = bundle_layout
    assert config.ENGINE_CONFIG_PATH == internal / "engine.yaml"
    assert config.PROMPT_TEMPLATE_PATH == internal / "prompt_template.yaml"
    assert config.FRONTEND_DIST == internal / "frontend" / "dist"
    assert config.has_bundled_frontend()


def test_runtime_paths_stay_next_to_exe(bundle_layout):
    exe_dir, _ = bundle_layout
    assert config.WORLD_PACK_PATH == exe_dir / "world_pack.yaml"
    assert config.DATA_DIR == exe_dir / "data"
    assert config.SESSION_STATE_PATH == exe_dir / "session_state.yaml"


def test_validate_bundle_assets_ok(bundle_layout):
    assert config.validate_bundle_assets() == []


def test_validate_bundle_assets_detects_missing(bundle_layout, monkeypatch):
    _, internal = bundle_layout
    (internal / "engine.yaml").unlink()
    missing = config.validate_bundle_assets()
    assert any("engine.yaml" in p for p in missing)


def test_ensure_runtime_files_copies_defaults(bundle_layout):
    exe_dir, internal = bundle_layout
    config.ensure_runtime_files()
    assert (exe_dir / "data" / "apikey.json").is_file()
    assert (exe_dir / "world_pack.yaml").is_file()
    assert not (internal / "data").exists()

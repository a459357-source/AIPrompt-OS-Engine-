"""Release versioning helpers."""
import config


def test_bump_patch_version():
    assert config.bump_patch_version("2.0.0") == "2.0.1"
    assert config.bump_patch_version("2.0.9") == "2.0.10"


def test_release_zip_basename():
    assert config.release_zip_basename("2.0.1") == "PromptOS-win64-v2.0.1"


def test_persist_app_version(tmp_path, monkeypatch):
    cfg = tmp_path / "config.py"
    eng = tmp_path / "engine.yaml"
    cfg.write_text('APP_VERSION = "1.0.0"\n', encoding="utf-8")
    eng.write_text('engine:\n  version: "1.0.0"\n', encoding="utf-8")
    monkeypatch.setattr(config, "_CONFIG_PY_PATH", cfg)
    monkeypatch.setattr(config, "_ENGINE_YAML_PATH", eng)
    monkeypatch.setattr(config, "APP_VERSION", "1.0.0")

    config.persist_app_version("1.0.1")

    assert config.APP_VERSION == "1.0.1"
    assert 'APP_VERSION = "1.0.1"' in cfg.read_text(encoding="utf-8")
    assert 'version: "1.0.1"' in eng.read_text(encoding="utf-8")

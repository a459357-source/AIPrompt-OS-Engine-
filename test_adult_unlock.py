"""Tests for adult mode unlock keys."""
import pytest

import config
from engine.adult_unlock import (
    generate_unlock_key,
    normalize_unlock_key,
    verify_unlock_key,
    write_secret,
)


@pytest.fixture
def unlock_env(tmp_path, monkeypatch):
    secret_path = tmp_path / "adult_unlock_secret"
    settings_path = tmp_path / "apikey.json"
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "APIKEY_PATH", settings_path)
    secret = write_secret()
    return {"secret": secret, "settings_path": settings_path}


def test_generate_and_verify_unlock_key(unlock_env):
    key = generate_unlock_key(secret=unlock_env["secret"])
    assert key.startswith("POS-A-")
    assert verify_unlock_key(key, secret=unlock_env["secret"])


def test_invalid_unlock_key_rejected(unlock_env):
    assert not verify_unlock_key("POS-A-INVALID1-INVALIDSIG123456", secret=unlock_env["secret"])


def test_save_adult_unlock_key_and_enable_mode(unlock_env):
    key = generate_unlock_key(secret=unlock_env["secret"])
    config.save_adult_unlock_key(key)
    assert config.is_adult_unlocked()
    config.save_adult_mode(True)
    config.reload_app_behavior()
    assert config.ADULT_MODE is True


def test_adult_mode_requires_unlock(unlock_env, monkeypatch):
    monkeypatch.delenv("PROMPTOS_SKIP_ADULT_UNLOCK", raising=False)
    with pytest.raises(ValueError, match="解锁密钥"):
        config.save_adult_mode(True)


def test_adult_mode_off_without_valid_stored_key(unlock_env, monkeypatch):
    monkeypatch.delenv("PROMPTOS_SKIP_ADULT_UNLOCK", raising=False)
    config._update_settings(adult_mode=True, adult_unlock_key="POS-A-BADKEY01-BADSIG123456789")
    config.reload_app_behavior()
    assert config.ADULT_MODE is False


def test_normalize_unlock_key_strips_spaces(unlock_env):
    key = generate_unlock_key(secret=unlock_env["secret"])
    spaced = f"{key[:7]} {key[7:]}"
    assert verify_unlock_key(spaced, secret=unlock_env["secret"])
    assert normalize_unlock_key(spaced) == normalize_unlock_key(key)

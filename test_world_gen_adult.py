"""Tests for world-gen adult mode prompt helpers."""

import config


def test_world_gen_adult_off():
    config.save_adult_mode(False)
    config.reload_adult_mode()
    assert config.world_gen_adult_requirements_suffix() == ""
    assert "Galgame" in config.world_gen_system_prompt()
    assert "unrestricted" not in config.world_gen_field_system_prompt()


def test_world_gen_adult_on():
    config.save_adult_mode(True)
    config.reload_adult_mode()
    suffix = config.world_gen_adult_requirements_suffix()
    assert "成人向设定" in suffix
    assert "禁止男男" in suffix or "禁止男" in suffix
    assert "unrestricted" in config.world_gen_system_prompt()
    assert "unrestricted" in config.world_gen_field_system_prompt()

    config.save_adult_mode(False)
    config.reload_adult_mode()

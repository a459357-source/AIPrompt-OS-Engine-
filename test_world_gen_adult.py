"""Tests for world-gen adult mode prompt helpers."""

import config


def test_world_gen_adult_off():
    config.save_adult_mode(False)
    config.reload_adult_mode()
    assert config.world_gen_adult_requirements_suffix() == ""
    assert config.world_gen_adult_requirements_body() == ""
    assert "Galgame" in config.world_gen_system_prompt()
    assert "unrestricted" not in config.world_gen_field_system_prompt()


def test_world_gen_adult_on():
    config.save_adult_mode(True)
    config.reload_adult_mode()
    suffix = config.world_gen_adult_requirements_suffix()
    body = config.world_gen_adult_requirements_body()
    assert "成人向设定" in suffix
    assert "genre 须包含" in body
    assert "禁止男男" in suffix or "禁止男" in suffix
    assert "unrestricted" in config.world_gen_system_prompt()
    assert "unrestricted" in config.world_gen_field_system_prompt()
    assert "成人向" in config.world_gen_task_intro()

    config.save_adult_mode(False)
    config.reload_adult_mode()


def test_world_gen_adult_override_without_global():
    config.save_adult_mode(False)
    config.reload_adult_mode()
    assert config.world_gen_adult_requirements_body(adult_mode=True)
    assert not config.world_gen_adult_requirements_body(adult_mode=False)


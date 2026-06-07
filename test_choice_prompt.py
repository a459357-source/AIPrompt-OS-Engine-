"""Tests that player choice is injected into the prompt for the same turn."""
from engine.builder import _player_choice_prompt


def test_choice_prompt_uses_current_option_text():
    state = {
        "history": [{
            "turn": 1,
            "options": [
                "向左走 → 发现密道",
                "向右走 → 遇到守卫",
                "原路返回",
                "大声呼救",
            ],
        }],
    }
    text = _player_choice_prompt("B", state)
    assert "选项 B" in text
    assert "遇到守卫" in text
    assert "本轮" in text
    assert "不得推迟" in text


def test_choice_prompt_custom_action():
    state = {"history": [{"turn": 2, "options": ["A", "B", "C", "D"]}]}
    text = _player_choice_prompt("悄悄翻窗离开", state)
    assert "自定义行动" in text
    assert "翻窗" in text

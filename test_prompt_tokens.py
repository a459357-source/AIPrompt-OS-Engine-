"""Prompt token budget tests (V2 target ~7k)."""
from unittest.mock import patch

from engine.builder import build_prompt


def test_prompt_under_budget_with_long_history():
    long_history = [
        {
            "turn": i,
            "scene": "场景",
            "status": "BUILD",
            "choice": "A",
            "story": "历史正文" * 80,
            "summary": "摘要",
            "options": ["opt"] * 4,
        }
        for i in range(1, 51)
    ]
    session = {
        "turn": 50,
        "scene": "当前场景",
        "status": "TENSION",
        "chapter": 2,
        "characters": {"A": {"name": "主角", "level": "L2", "role": "主角"}},
        "history": long_history,
    }
    world = {
        "world": {
            "title": "测试世界",
            "setting": "设定",
            "main_goal": "目标",
            "characters": [{"name": "主角", "is_main": True, "role_tags": ["主角"]}],
            "relationship_system": {"stages": ["陌生", "朋友"], "affection": 0},
        }
    }
    memory = {"characters": {}, "world_flags": []}

    with patch("engine.builder.io_utils.read_yaml") as ry, \
         patch("engine.builder.load_memory", return_value=memory), \
         patch("engine.memory_layers.load_world_summary_text", return_value="世界: 测试"), \
         patch("engine.memory_layers.load_chapter_summaries", return_value=[]):
        def _yaml(path, use_cache=True):
            p = str(path)
            if "session" in p:
                return session
            if "world_pack" in p or "world" in p:
                return world
            if "engine" in p:
                return {"rules": []}
            return {
                "system": "sys {{FORCE_EVENT_NOTICE}} {{STORY_LENGTH}} {{STORY_LENGTH_MIN}} {{STORY_LENGTH_MAX}} {{AI_BEHAVIOR_RULES}} {{OPTION_COUNT}} {{CUSTOM_RULES}} {{MAIN_GOAL}}",
                "user": "{{WORLD}}\n{{LONG_TERM_MEMORY}}\n{{RECENT_SUMMARIES}}\n{{HOT_CONTEXT}}\n{{LAST_CHOICE}}\n{{CHARACTERS_CONTEXT}}\n{{RELATIONSHIP_SYSTEM}}\n{{ENGINE_RULES}}\n{{FORCE_EVENT_PROMPT}}",
            }
        ry.side_effect = _yaml

        system, user = build_prompt(current_choice="A")
        est = int((len(system) + len(user)) * 0.6)
        assert est < 12000, f"prompt too large: ~{est} tokens"

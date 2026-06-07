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
                "user": "{{WORLD}}\n{{LONG_TERM_MEMORY}}\n{{RECENT_SUMMARIES}}\n{{HOT_CONTEXT}}\n{{LAST_CHOICE}}\n{{CHARACTERS_CONTEXT}}\n{{CHARACTER_BRAIN}}\n{{RELATIONSHIP_SYSTEM}}\n{{ENGINE_RULES}}\n{{FORCE_EVENT_PROMPT}}",
            }
        ry.side_effect = _yaml

        system, user = build_prompt(current_choice="A")
        est = int((len(system) + len(user)) * 0.6)
        assert est < 12000, f"prompt too large: ~{est} tokens"


def test_prompt_router_filters_unrelated_factions():
    session = {
        "turn": 12,
        "scene": "皇宫议事厅",
        "status": "TENSION",
        "chapter": 1,
        "characters": {"p": {"name": "长公主", "level": "L2"}},
        "history": [
            {
                "turn": 11,
                "scene": "皇宫议事厅",
                "status": "TENSION",
                "choice": "A",
                "story": "长公主主持朝议。",
                "summary": "朝议",
                "options": ["A", "B", "C", "D"],
            },
        ],
    }
    world = {
        "world": {
            "title": "王朝",
            "setting": "古代宫廷",
            "main_goal": "在皇宫保护长公主",
            "characters": [
                {
                    "name": "长公主",
                    "factionMemberships": [{"faction": "皇室", "visibility": "public"}],
                },
            ],
            "relationship_system": {"stages": ["陌生", "盟友"], "affection": 40},
        },
    }
    memory = {
        "characters": {
            "长公主": {"trust": 0.7, "relationship": "盟友", "flags": [], "tier": "核心", "last_appearance_turn": 12},
        },
        "factions": {
            "皇室": {
                "reputation": 0.8,
                "type": "kingdom",
                "goals": ["巩固皇权"],
                "resources": ["禁军"],
                "influence": 90,
                "flags": [],
                "controlledTerritories": ["皇宫", "帝都"],
                "subordinateOrganizations": ["内廷"],
                "keyAssets": ["玉玺"],
                "power": {"military": 80, "economic": 70, "political": 90, "technology": 40},
                "relation_to_player": "ally",
            },
            "北境联盟": {
                "reputation": 0.4,
                "type": "kingdom",
                "goals": ["南下"],
                "resources": ["骑兵"],
                "influence": 60,
                "flags": [],
                "controlledTerritories": ["北境关隘"],
                "subordinateOrganizations": ["北境军团"],
                "keyAssets": ["寒铁"],
                "power": {"military": 75, "economic": 30, "political": 40, "technology": 35},
                "relation_to_player": "hostile",
            },
            "江湖门派": {
                "reputation": 0.5,
                "type": "guild",
                "goals": ["广收门徒"],
                "resources": ["弟子"],
                "influence": 40,
                "flags": [],
                "controlledTerritories": ["武当山"],
                "subordinateOrganizations": ["外门"],
                "keyAssets": ["剑谱"],
                "power": {"military": 50, "economic": 20, "political": 20, "technology": 30},
                "relation_to_player": "neutral",
            },
            "海外商会": {
                "reputation": 0.5,
                "type": "corporation",
                "goals": ["垄断海运"],
                "resources": ["商船"],
                "influence": 45,
                "flags": [],
                "controlledTerritories": ["海外港口"],
                "subordinateOrganizations": ["船队"],
                "keyAssets": ["航线"],
                "power": {"military": 20, "economic": 80, "political": 30, "technology": 50},
                "relation_to_player": "neutral",
            },
        },
        "world_flags": [],
    }

    with patch("engine.builder.io_utils.read_yaml") as ry, \
         patch("engine.builder.load_memory", return_value=memory), \
         patch("engine.memory_layers.load_chapter_summaries", return_value=[]), \
         patch("engine.memory_layers.load_world_summary_text") as load_world:
        load_world.return_value = "世界: 王朝\n【主要势力】\n  - 皇室: 帝都"

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
                "user": "{{WORLD}}\n{{LONG_TERM_MEMORY}}\n{{RECENT_SUMMARIES}}\n{{HOT_CONTEXT}}\n{{LAST_CHOICE}}\n{{CHARACTERS_CONTEXT}}\n{{CHARACTER_BRAIN}}\n{{RELATIONSHIP_SYSTEM}}\n{{ENGINE_RULES}}\n{{FORCE_EVENT_PROMPT}}",
            }
        ry.side_effect = _yaml

        system, user = build_prompt(current_choice="A")
        est = int((len(system) + len(user)) * 0.6)
        assert est < 12000, f"prompt too large: ~{est} tokens"
        assert user.count("海外商会") <= user.count("皇室")
        assert user.count("江湖门派") <= user.count("长公主")


def test_prompt_includes_director_advice_placeholder():
    session = {
        "turn": 15,
        "scene": "场景",
        "status": "BUILD",
        "chapter": 1,
        "characters": {},
        "history": [{"turn": 14, "options": ["a", "b", "c", "d"]}],
    }
    world = {"world": {"title": "T", "main_goal": "拯救王国", "characters": []}}
    plot_state = {
        "main_plot": {"name": "拯救王国", "progress": 5, "stage": 1},
        "unresolved_hooks": [],
        "resolved_hooks": [],
        "last_progress_turn": 0,
        "last_analysis_turn": 0,
    }

    with patch("engine.builder.io_utils.read_yaml") as ry, \
         patch("engine.builder.load_memory", return_value={}), \
         patch("engine.builder.ensure_plot_state", return_value=plot_state), \
         patch("engine.builder.build_director_advice", return_value="【剧情导演建议】测试"), \
         patch("engine.builder.build_hot_context", return_value="HOT"), \
         patch("engine.builder.build_long_term_memory", return_value=""), \
         patch("engine.builder.build_recent_summaries", return_value=""), \
         patch("engine.builder.load_world_summary_text", return_value="世界"), \
         patch("engine.memory_layers.load_chapter_summaries", return_value=[]):
        template = {
            "system": "sys {{FORCE_EVENT_NOTICE}} {{STORY_LENGTH}} {{STORY_LENGTH_MIN}} {{STORY_LENGTH_MAX}} {{AI_BEHAVIOR_RULES}} {{OPTION_COUNT}} {{CUSTOM_RULES}} {{MAIN_GOAL}}",
            "user": "{{WORLD}}\n{{HOT_CONTEXT}}\n{{DIRECTOR_ADVICE}}\n{{LAST_CHOICE}}",
        }

        def _yaml(path, use_cache=True):
            p = str(path).replace("\\", "/")
            if "session_state" in p:
                return session
            if "world_pack" in p:
                return world
            if p.endswith("engine.yaml"):
                return {"rules": []}
            if "prompt_template" in p:
                return template
            return template
        ry.side_effect = _yaml

        _, user = build_prompt(current_choice="A")
        assert "{{DIRECTOR_ADVICE}}" not in user
        assert "剧情导演建议" in user
        assert "测试" in user


def test_prompt_includes_objectives_context():
    session = {
        "turn": 5,
        "scene": "场景",
        "status": "BUILD",
        "chapter": 1,
        "characters": {},
        "history": [{"turn": 4, "options": ["a", "b", "c", "d"]}],
        "objectives": {
            "main": [{"id": "main_001", "title": "调查灭门案", "progress": 40, "status": "active"}],
            "side": [{"id": "side_001", "title": "参加诗会", "progress": 10, "status": "active"}],
        },
    }
    world = {"world": {"title": "T", "main_goal": "调查灭门案", "characters": []}}

    with patch("engine.builder.io_utils.read_yaml") as ry, \
         patch("engine.builder.load_memory", return_value={}), \
         patch("engine.builder.ensure_plot_state", return_value={}), \
         patch("engine.builder.build_director_advice", return_value=""), \
         patch("engine.builder.build_hot_context", return_value="HOT"), \
         patch("engine.builder.build_long_term_memory", return_value=""), \
         patch("engine.builder.build_recent_summaries", return_value=""), \
         patch("engine.builder.load_world_summary_text", return_value="世界"), \
         patch("engine.memory_layers.load_chapter_summaries", return_value=[]):
        template = {
            "system": "sys {{FORCE_EVENT_NOTICE}} {{STORY_LENGTH}} {{STORY_LENGTH_MIN}} {{STORY_LENGTH_MAX}} {{AI_BEHAVIOR_RULES}} {{OPTION_COUNT}} {{CUSTOM_RULES}} {{MAIN_GOAL}}",
            "user": "{{WORLD}}\n{{HOT_CONTEXT}}\n{{OBJECTIVES_CONTEXT}}\n{{DIRECTOR_ADVICE}}\n{{LAST_CHOICE}}",
        }

        def _yaml(path, use_cache=True):
            p = str(path).replace("\\", "/")
            if "session_state" in p:
                return session
            if "world_pack" in p:
                return world
            if p.endswith("engine.yaml"):
                return {"rules": []}
            if "prompt_template" in p:
                return template
            return template
        ry.side_effect = _yaml

        _, user = build_prompt(current_choice="A")
        assert "{{OBJECTIVES_CONTEXT}}" not in user
        assert "当前目标" in user
        assert "调查灭门案" in user
        assert "参加诗会" in user

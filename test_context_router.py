"""Tests for V3 Context Router."""
from unittest.mock import patch

import config
from engine.context_router import (
    collect_context_items,
    route_context_for_prompt,
    route_world_summary_factions,
    score_context_items,
    select_context_items,
    build_router_inputs,
    ContextItem,
)
from engine.memory_layers import build_long_term_memory


def _palace_fixture():
    session = {
        "turn": 20,
        "scene": "皇宫内苑",
        "status": "TENSION",
        "characters": {
            "p": {"name": "长公主", "level": "L2"},
        },
    }
    memory = {
        "characters": {
            "长公主": {
                "trust": 0.7,
                "relationship": "盟友",
                "flags": [],
                "tier": "核心",
                "last_appearance_turn": 20,
            },
            "北境使者": {
                "trust": 0.3,
                "relationship": "中立",
                "flags": [],
                "tier": "背景",
                "last_appearance_turn": 2,
            },
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
                "goals": ["南下扩张"],
                "resources": ["骑兵"],
                "influence": 60,
                "flags": [],
                "controlledTerritories": ["北境关隘", "雪原"],
                "subordinateOrganizations": ["北境军团"],
                "keyAssets": ["寒铁"],
                "power": {"military": 75, "economic": 30, "political": 40, "technology": 35},
                "relation_to_player": "hostile",
            },
        },
        "world_events": [],
        "world_flags": [],
    }
    world_pack = {
        "world": {
            "main_goal": "在皇宫中保护长公主并稳固朝局",
            "characters": [
                {
                    "name": "长公主",
                    "is_main": False,
                    "factionMemberships": [{"faction": "皇室", "visibility": "public"}],
                },
            ],
        },
    }
    return session, memory, world_pack


def test_scoring_princess_beats_north_faction():
    session, memory, world_pack = _palace_fixture()
    inputs = build_router_inputs(session, memory, world_pack)
    items = collect_context_items(memory, session, world_pack)
    scored = score_context_items(items, inputs)
    by_id = {it.id: it.score for it in scored}

    assert by_id.get("npc_长公主", 0) >= 100
    assert by_id.get("faction_皇室", 0) > by_id.get("faction_北境联盟", 0)
    assert by_id.get("npc_北境使者", 0) < by_id.get("npc_长公主", 0)


def test_select_top_n():
    items = [
        ContextItem(id=f"item_{i}", kind="npc", text=f"line {i}", score=i, priority=i)
        for i in range(30)
    ]
    selected = select_context_items(items, 20)
    assert len(selected) == 20
    assert selected[0].score == 29


def test_route_context_respects_max_items():
    session, memory, world_pack = _palace_fixture()
    with patch.object(config, "MAX_CONTEXT_ITEMS", 3):
        text = route_context_for_prompt(memory, session, world_pack, max_items=3)
    assert text
    assert text.count("  ") >= 1


def test_router_disabled_matches_legacy_blocks():
    session, memory, world_pack = _palace_fixture()
    with patch.object(config, "CONTEXT_ROUTER_ENABLED", False):
        legacy = build_long_term_memory(memory, session, world_pack=world_pack)
    assert "【角色关系记忆】" in legacy or "长公主" in legacy
    assert "【势力状态】" in legacy
    assert "皇室" in legacy


def test_router_enabled_reduces_irrelevant_faction_scope():
    session, memory, world_pack = _palace_fixture()
    with patch.object(config, "CONTEXT_ROUTER_ENABLED", True):
        routed = build_long_term_memory(memory, session, world_pack=world_pack)
    assert "长公主" in routed or "皇室" in routed
    assert "北境联盟" not in routed


def test_token_band_router_on_off():
    session = {
        "turn": 20,
        "scene": "皇宫内苑",
        "status": "TENSION",
        "characters": {"p": {"name": "长公主", "level": "L2"}},
    }
    memory = {
        "characters": {
            "长公主": {
                "trust": 0.7,
                "relationship": "盟友",
                "flags": ["结盟"],
                "tier": "核心",
                "last_appearance_turn": 20,
            },
        },
        "factions": {
            "皇室": {
                "reputation": 0.8,
                "type": "kingdom",
                "goals": ["巩固皇权"],
                "resources": ["禁军"],
                "influence": 90,
                "flags": ["朝议"],
                "controlledTerritories": ["皇宫", "帝都"],
                "subordinateOrganizations": ["内廷"],
                "keyAssets": ["玉玺"],
                "power": {"military": 80, "economic": 70, "political": 90, "technology": 40},
                "relation_to_player": "ally",
            },
        },
        "world_events": [],
        "world_flags": ["朝局动荡"],
    }
    world_pack = {
        "world": {
            "main_goal": "在皇宫中保护长公主并稳固朝局",
            "characters": [
                {
                    "name": "长公主",
                    "factionMemberships": [{"faction": "皇室", "visibility": "public"}],
                },
            ],
        },
    }
    from engine.memory_layers import _legacy_context_block

    off = _legacy_context_block(memory, session)
    on = route_context_for_prompt(
        memory,
        session,
        world_pack,
        baseline_chars=len(off),
    )
    est_off = int(len(off) * 0.6)
    est_on = int(len(on) * 0.6)
    if est_off > 0:
        delta = abs(est_on - est_off) / est_off
        assert delta <= 0.10, f"token delta {delta:.1%} exceeds 10%"


def test_route_world_summary_factions():
    session, memory, world_pack = _palace_fixture()
    factions = [
        {"name": "皇室", "description": "帝都统治集团", "controlledTerritories": ["皇宫"]},
        {"name": "北境联盟", "description": "北方军阀", "controlledTerritories": ["北境关隘"]},
        {"name": "海外商会", "description": "远洋贸易", "controlledTerritories": ["港口"]},
    ]
    selected = route_world_summary_factions(
        factions, session, memory, world_pack, regions=["皇宫", "北境关隘"],
    )
    names = [f["name"] for f in selected]
    assert "皇室" in names
    assert "海外商会" not in names

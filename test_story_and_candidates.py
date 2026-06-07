"""Tests for story length clamp and candidate NPC pool."""
import json

import config
from engine.story_length import count_story_chars, clamp_story_text
from engine.memory_names import assess_npc_name, NameVerdict, GENERIC_NPC_NAMES
from engine.candidate_npcs import load_pool, save_pool, try_register_sighting, reset_pool
from engine.memory import load_memory, save_memory


def test_clamp_story_at_sentence():
    text = "第一句。" + "填充" * 200 + "最后一句。"
    max_len = 50
    clamped, did = clamp_story_text(text, max_len)
    assert did
    assert count_story_chars(clamped) <= max_len


def test_generic_npc_rejected():
    assert assess_npc_name("路人") == NameVerdict.REJECT
    assert assess_npc_name("路人") == NameVerdict.REJECT
    assert "路人" in GENERIC_NPC_NAMES


def test_long_name_rejected():
    assert assess_npc_name("来自深渊的影之行者") == NameVerdict.REJECT


def test_title_pattern_low_weight():
    assert assess_npc_name("影之行者") == NameVerdict.ACCEPT
    assert assess_npc_name("深渊使者") == NameVerdict.LOW_WEIGHT


def test_candidate_promotion_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CANDIDATE_NPCS_PATH", tmp_path / "candidate_npcs.json")
    monkeypatch.setattr(config, "MEMORY_PATH", tmp_path / "memory.json")
    reset_pool(persist=True)
    save_memory({"characters": {}}, persist=True)
    memory = load_memory()
    world = {"world": {"characters": [{"name": "主角", "isMain": True}]}}

    try_register_sighting("影之行者", 1, memory, world)
    assert load_pool()["影之行者"]["appear_count"] == 1
    assert "影之行者" not in memory["characters"]

    try_register_sighting("影之行者", 2, memory, world)
    assert "影之行者" in memory["characters"]
    assert memory["characters"]["影之行者"]["npc_stage"] == "incubating"

    try_register_sighting("影之行者", 3, memory, world)
    assert memory["characters"]["影之行者"]["npc_stage"] == "active"

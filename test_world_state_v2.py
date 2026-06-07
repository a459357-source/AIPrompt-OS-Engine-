"""world_state_v2 与压力校验 smoke tests"""
from engine.analytics import compute_all, world_state_v2


def test_world_state_v2_keys():
    ws = world_state_v2()
    assert "location" in ws
    assert "world_time" in ws
    assert "factions" in ws
    assert "events" in ws
    assert "relationship_network" in ws
    assert "turn" in ws["world_time"]
    assert "nodes" in ws["relationship_network"]


def test_world_state_v2_relationship_edges_from_types(monkeypatch):
    """NPC relationship_type / trust should produce protagonist edges."""
    from engine.analytics import world_state_v2
    import engine.analytics as analytics_mod
    import config

    def fake_yaml(path):
        if path == config.SESSION_STATE_PATH:
            return {
                "turn": 5,
                "chapter": 1,
                "scene": "测试场景",
                "characters": {
                    "hero": {"name": "林夜", "role": "主角"},
                    "npc1": {"name": "艾拉", "role": "NPC", "relationship": ["同伴"]},
                },
            }
        if path == config.WORLD_PACK_PATH:
            return {
                "world": {
                    "title": "Test",
                    "characters": [
                        {"name": "林夜", "isMain": True},
                        {"name": "艾拉", "isMain": False, "faction": "自由阵线"},
                    ],
                    "factions": [{"name": "自由阵线"}],
                },
                "custom": {"characterRelations": {}},
            }
        return {}

    def fake_json(path):
        if path == config.MEMORY_PATH:
            return {
                "characters": {
                    "林夜": {"trust": 1.0},
                    "艾拉": {"trust": 0.72, "relationship_type": "lover"},
                },
                "factions": {
                    "自由阵线": {"reputation": 0.6, "leader": "艾拉", "relation_to_player": "ally"},
                },
                "faction_attitudes": {},
            }
        return {}

    monkeypatch.setattr(analytics_mod.io_utils, "read_yaml", fake_yaml)
    monkeypatch.setattr(analytics_mod.io_utils, "read_json", fake_json)
    monkeypatch.setattr(analytics_mod, "_canonical_character_names", lambda memory=None: ["林夜", "艾拉"])

    ws = world_state_v2()
    edges = ws["relationship_network"]["edges"]
    kinds = {(e["from"], e["to"], e["kind"]) for e in edges}
    assert ("林夜", "艾拉", "relation") in kinds
    assert ("艾拉", "自由阵线", "member_of") in kinds


def test_compute_all_includes_world_state_v2():
    data = compute_all()
    assert "world_state_v2" in data
    assert isinstance(data["world_state_v2"]["factions"], list)

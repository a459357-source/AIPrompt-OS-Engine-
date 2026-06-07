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


def test_compute_all_includes_world_state_v2():
    data = compute_all()
    assert "world_state_v2" in data
    assert isinstance(data["world_state_v2"]["factions"], list)

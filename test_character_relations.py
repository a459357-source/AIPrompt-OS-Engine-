"""Tests for multidimensional character relation normalization."""
from ui.routes.world import _link_character_factions, _normalize_character_relations


def test_normalize_character_relations_clamps_and_tags():
    raw = {
        "维克托": {
            "relationshipType": "rival",
            "affection": 120,
            "trust": "40",
            "respect": 70,
            "dependence": 20,
            "hostility": 85,
            "attraction": -5,
            "tags": ["  竞争意识 ", "", "秘密共享", "无效"],
        }
    }
    out = _normalize_character_relations(raw, ["维克托", "未知"])
    assert "维克托" in out
    assert "未知" in out
    assert out["维克托"]["relationshipType"] == "rival"
    assert out["维克托"]["affection"] == 100
    assert out["维克托"]["trust"] == 40
    assert out["维克托"]["attraction"] == 0
    assert out["维克托"]["tags"] == ["竞争意识", "秘密共享", "无效"]
    assert out["未知"]["tags"] == []


def test_normalize_character_relations_invalid_type_fallback():
    out = _normalize_character_relations(
        {"NPC": {"relationshipType": "unknown", "tags": "青梅竹马"}},
        ["NPC"],
    )
    assert out["NPC"]["relationshipType"] == "friend"
    assert out["NPC"]["tags"] == ["青梅竹马"]


def test_link_character_factions_by_leader():
    factions = [
        {"name": "银翼商会", "leader": "维克托"},
        {"name": "夜鸦团", "leader": "菲尔德"},
    ]
    characters = [
        {"name": "维克托", "faction": ""},
        {"name": "菲尔德", "faction": "夜鸦团"},
        {"name": "主角", "faction": "不存在"},
    ]
    out = _link_character_factions(characters, factions)
    assert out[0]["faction"] == "银翼商会"
    assert out[0]["factionMemberships"] == [{"faction": "银翼商会", "visibility": "public"}]
    assert out[1]["faction"] == "夜鸦团"
    assert out[2]["faction"] == ""


def test_link_character_factions_multi_membership():
    factions = [
        {"name": "星穹学院", "leader": "苏浅"},
        {"name": "暗域议会", "leader": ""},
    ]
    characters = [
        {
            "name": "陈默",
            "factionMemberships": [
                {"faction": "暗域议会", "visibility": "public"},
                {"faction": "星穹学院", "visibility": "hidden"},
            ],
        },
    ]
    out = _link_character_factions(characters, factions)
    assert len(out[0]["factionMemberships"]) == 2
    assert out[0]["factionMemberships"][1]["visibility"] == "hidden"
    assert out[0]["faction"] == "暗域议会"


def test_remap_relation_keys_fuzzy():
    from ui.routes.world import _remap_relation_keys

    raw = {"维克托·菲尔德": {"relationshipType": "rival", "tags": ["竞争意识"]}}
    out = _remap_relation_keys(raw, ["维克托"])
    assert "维克托" in out
    assert out["维克托"]["relationshipType"] == "rival"


def test_link_artifact_owners():
    from ui.routes.world import _link_artifact_owners

    artifacts = [{"name": "信物", "ownerType": "character", "ownerId": "维克托·某"}]
    characters = [{"name": "维克托"}]
    out = _link_artifact_owners(artifacts, characters, [])
    assert out[0]["ownerId"] == "维克托"

"""Bootstrap isolated game state from a regression scenario fixture."""
from __future__ import annotations

import copy
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import config
from engine import io_utils
from engine.character_brain import normalize_personality, seed_personality_from_world
from engine.character_registry import initial_relation_label
from engine.memory_layers import build_world_summary_from_pack
from engine.objective_system import default_objectives
from engine.plot_director import init_plot_state
from engine.state_store import commit_bundle

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"

_CONFIG_PATH_KEYS = (
    "DATA_DIR",
    "SESSION_STATE_PATH",
    "MEMORY_PATH",
    "STORY_GRAPH_PATH",
    "PLOT_STATE_PATH",
    "WORLD_INIT_PATH",
    "WORLD_PACK_PATH",
    "API_USAGE_PATH",
    "CHAPTER_PATH",
    "WORLD_SUMMARY_PATH",
    "CANDIDATE_NPCS_PATH",
    "RUNTIME_MEMORY_PATH",
    "CHAPTER_SUMMARIES_PATH",
    "TURN_PROFILE_PATH",
)


@dataclass
class Scenario:
    id: str
    category: str
    label: str
    seed: int
    scene: str
    main_goal: str
    world_pack: dict
    character_relations: dict = field(default_factory=dict)
    adult_settings: dict = field(default_factory=dict)

    @property
    def prefer_relationship_choice(self) -> bool:
        return self.category in ("D", "E")


def list_scenario_files() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("*.json"))


def load_scenario(scenario_id: str | None = None) -> Scenario:
    files = list_scenario_files()
    if not files:
        raise FileNotFoundError(f"No scenarios in {SCENARIOS_DIR}")

    if scenario_id:
        match = [f for f in files if f.stem == scenario_id or f.stem.startswith(scenario_id)]
        if not match:
            raise FileNotFoundError(f"Scenario not found: {scenario_id}")
        path = match[0]
    else:
        path = files[0]

    raw = json.loads(path.read_text(encoding="utf-8"))
    world = raw.get("world_pack", {}).get("world", raw.get("world_pack", {}))
    return Scenario(
        id=str(raw.get("id", path.stem)),
        category=str(raw.get("category", "?")),
        label=str(raw.get("label", path.stem)),
        seed=int(raw.get("seed", 0)),
        scene=str(raw.get("scene", world.get("locations", [{}])[0].get("name", "初始场景"))),
        main_goal=str(raw.get("main_goal", world.get("main_goal", ""))),
        world_pack=raw["world_pack"] if "world_pack" in raw else {"world": raw["world"]},
        character_relations=dict(raw.get("character_relations") or {}),
        adult_settings=dict(raw.get("adult_settings") or {}),
    )


def load_all_scenarios() -> list[Scenario]:
    return [load_scenario(f.stem) for f in list_scenario_files()]


def _normalize_character_personality(char_data: dict) -> None:
    char_data["personality"] = seed_personality_from_world(char_data)
    char_data["personality"] = normalize_personality(char_data["personality"])


def _build_runtime_from_scenario(scenario: Scenario) -> None:
    world_pack = copy.deepcopy(scenario.world_pack)
    world = world_pack.setdefault("world", {})
    scene = scenario.scene
    main_goal = scenario.main_goal or str(world.get("main_goal", "")).strip()
    world["main_goal"] = main_goal

    if not world.get("locations"):
        world["locations"] = [{"name": scene, "desc": "初始场景"}]

    rel_config = world.get("relationship_system") or {
        "stages": ["陌生", "认识", "信赖", "盟友", "羁绊"],
        "affection": 0,
    }
    world["relationship_system"] = rel_config

    chars = world.get("characters") or []
    for ch in chars:
        if isinstance(ch, dict):
            _normalize_character_personality(ch)

    io_utils.write_yaml(config.WORLD_PACK_PATH, world_pack)
    io_utils.write_json(config.WORLD_SUMMARY_PATH, build_world_summary_from_pack(world_pack))

    state_chars: dict[str, dict] = {}
    mem_chars: dict[str, dict] = {}
    init_affection = rel_config.get("affection", 0)
    char_relations = scenario.character_relations
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for i, ch in enumerate(chars):
        if i >= len(letters) or not isinstance(ch, dict):
            break
        key = letters[i]
        name = str(ch.get("name", f"角色{i + 1}")).strip()
        is_main = bool(ch.get("is_main", ch.get("isMain", False)))
        role_tags = ch.get("role_tags", [])
        if isinstance(role_tags, str):
            role_tags = [role_tags]
        role_str = " / ".join(role_tags) if role_tags else str(ch.get("role", ""))
        personality_tags = ch.get("personality_tags", [])
        if isinstance(personality_tags, str):
            personality_tags = [personality_tags]
        relationship = ch.get("relationship", [])
        if isinstance(relationship, str):
            relationship = [relationship]

        note_parts = []
        for label, val in (
            ("外貌", ch.get("appearance", "")),
            ("性格", " / ".join(personality_tags) if personality_tags else ""),
            ("关系", " / ".join(relationship) if relationship and not is_main else ""),
            ("目标", ch.get("goal", "")),
            ("秘密", ch.get("secret", "")),
        ):
            if val:
                note_parts.append(f"{label}：{val}")
        note = "\n".join(note_parts)

        relation_label = initial_relation_label(
            name,
            is_main=is_main,
            relationship=relationship,
            char_relations=char_relations,
        )
        state_chars[key] = {
            "name": name,
            "role": role_str,
            "level": "L0",
            "relation": relation_label,
            "note": note,
        }
        initial_trust = init_affection / 100.0 if init_affection > 0 else 0.5
        mem_rel = f"{role_str}，主角" if is_main and role_str else relation_label
        mem_chars[name] = {
            "trust": initial_trust,
            "flags": [],
            "relationship": mem_rel,
            "personality": seed_personality_from_world(ch),
        }
        secret = str(ch.get("secret", "")).strip()
        if secret:
            mem_chars[name].setdefault("flags", []).append(f"隐藏秘密：{secret}")

    rel_metrics = ("trust", "affection", "respect", "dependence", "hostility", "attraction")
    for npc_name, rel in char_relations.items():
        if not isinstance(rel, dict) or npc_name not in mem_chars:
            continue
        entry = mem_chars[npc_name]
        for metric in rel_metrics:
            raw = rel.get(metric)
            if isinstance(raw, (int, float)):
                val = round(max(0.0, min(1.0, float(raw) / 100.0)), 2)
                entry[metric] = val
                entry.setdefault("metric_history", {}).setdefault(metric, []).append([0, val])

    initial_state = {
        "scene": scene,
        "status": "SETUP",
        "turn": 0,
        "characters": state_chars,
        "history": [],
        "force_event_pending": False,
        "chapter": 1,
        "objectives": default_objectives(main_goal),
    }
    initial_graph = {
        "nodes": {
            "0": {
                "turn": 0,
                "text": f"初始场景：{scene}",
                "scene": scene,
                "status": "SETUP",
                "choices": {},
                "parent": None,
                "choice_taken": None,
            }
        },
        "current_node": "0",
        "edges": [],
    }
    initial_memory = {
        "characters": mem_chars,
        "world_flags": [],
        "world_events": [],
        "global_trust": 0.5,
        "relationship_system": rel_config,
    }
    commit_bundle(initial_state, initial_memory, initial_graph, chapter="")
    plot_state = init_plot_state(world_pack)

    from engine.candidate_npcs import reset_pool

    reset_pool(persist=True)

    io_utils.write_json(config.WORLD_INIT_PATH, {
        "state": initial_state,
        "graph": initial_graph,
        "memory": initial_memory,
        "plot_state": plot_state,
    })


def _apply_adult_settings(settings: dict) -> None:
    defaults = {
        "adult_mode": True,
        "adult_profile": "adult_first",
        "content_weights": {"story": 0, "romance": 0, "adult": 100},
        "expression_style": "direct",
    }
    merged = {**defaults, **(settings or {})}
    config.save_adult_mode(bool(merged.get("adult_mode", True)))
    config.save_adult_profile(str(merged.get("adult_profile", "adult_first")))
    config.save_content_weights(dict(merged.get("content_weights", defaults["content_weights"])))
    config.save_expression_style(str(merged.get("expression_style", "direct")))
    config.reload_app_behavior()


def _apply_model(model: str = "deepseek-chat") -> None:
    config.save_model(model)
    config.reload_model()


@dataclass
class IsolatedRun:
    run_dir: Path
    scenario: Scenario
    architecture: str
    _saved_paths: dict[str, Any] = field(default_factory=dict, repr=False)
    _saved_env: str | None = field(default=None, repr=False)

    @property
    def run_id(self) -> str:
        return f"{self.scenario.id}_{self.architecture}"


@contextmanager
def isolated_run(
    scenario: Scenario,
    architecture: str,
    *,
    base_dir: Path | None = None,
    run_suffix: str | None = None,
) -> Iterator[IsolatedRun]:
    """
    Context manager: isolate DATA_DIR, bootstrap scenario, set prompt architecture.

    architecture: ``legacy`` | ``unified``
    """
    root = base_dir or (config.ROOT / "output" / "prompt_regression" / "runs")
    run_dir = root / (run_suffix or f"{scenario.id}_{architecture}")
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    ctx = IsolatedRun(run_dir=run_dir, scenario=scenario, architecture=architecture)

    for key in _CONFIG_PATH_KEYS:
        ctx._saved_paths[key] = getattr(config, key)

    ctx._saved_env = os.environ.get("PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE")

    try:
        config.DATA_DIR = data_dir
        config.SESSION_STATE_PATH = data_dir / "session_state.yaml"
        config.MEMORY_PATH = data_dir / "memory.json"
        config.STORY_GRAPH_PATH = data_dir / "story_graph.json"
        config.PLOT_STATE_PATH = data_dir / "plot_state.json"
        config.WORLD_INIT_PATH = data_dir / "world_init.json"
        config.WORLD_PACK_PATH = run_dir / "world_pack.yaml"
        config.API_USAGE_PATH = data_dir / "api_usage.jsonl"
        config.CHAPTER_PATH = data_dir / "chapter.md"
        config.WORLD_SUMMARY_PATH = data_dir / "world_summary.json"
        config.CANDIDATE_NPCS_PATH = data_dir / "candidate_npcs.json"
        config.RUNTIME_MEMORY_PATH = data_dir / "runtime_memory.json"
        config.CHAPTER_SUMMARIES_PATH = data_dir / "chapter_summaries.json"
        config.TURN_PROFILE_PATH = data_dir / "turn_profile.jsonl"

        if architecture == "legacy":
            os.environ["PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE"] = "1"
        else:
            os.environ.pop("PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE", None)

        _apply_adult_settings(scenario.adult_settings)
        _apply_model("deepseek-chat")
        _build_runtime_from_scenario(scenario)

        yield ctx
    finally:
        for key, val in ctx._saved_paths.items():
            setattr(config, key, val)
        if ctx._saved_env is None:
            os.environ.pop("PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE", None)
        else:
            os.environ["PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE"] = ctx._saved_env

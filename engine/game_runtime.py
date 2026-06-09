"""
game_runtime.py — V6 Game Runtime orchestrator
================================================
Wires narrative + visual into a unified game frame.
Single entry: build_game_frame(state, result) → hydrated game payload.

Design contract:
  - game = only orchestrator (never generates content itself)
  - narrative = world skeleton (nodes, choices, participants) — drives visual
  - visual = mandatory consequence of narrative node
  - UI = pure render (never triggers generation)
"""

# NARRATIVE SYSTEM IS PASSIVE ONLY — read-only metadata for UI/visuals.
# It must NEVER control story, options, or game flow.

from __future__ import annotations

import logging
import threading
from typing import Any

import config
from engine.visual.visual_api import public_image_url

logger = logging.getLogger(__name__)


# ── Narrative node resolution ───────────────────────────────────────

def resolve_game_narrative_node(scene_id: str) -> dict[str, Any]:
    """Resolve the narrative node for the current game scene.

    This is the bridge that connects game state → narrative system.
    Returns a lightweight node dict with event_id, context, characters, choices.
    """
    from engine.narrative.narrative_router import (
        get_choices_for_event,
        get_node_definition,
        resolve_canonical_event_id,
    )

    canonical = resolve_canonical_event_id(scene_id) if scene_id else ""
    node_def = get_node_definition(canonical) if canonical else {}
    choices = get_choices_for_event(canonical) if canonical else []

    # Extract participants from node definition (P0 patch field) or fallback
    participants: list[str] = []
    raw_participants = node_def.get("participants") if isinstance(node_def, dict) else None
    if isinstance(raw_participants, list):
        participants = [str(p).strip() for p in raw_participants if str(p).strip()]
    if not participants:
        # fallback: try to extract from context
        try:
            state = _read_session_state()
            chars = state.get("characters", {})
            participants = [str(ch.get("name") or k).strip() for k, ch in chars.items()
                            if isinstance(ch, dict) and str(ch.get("name") or k).strip()][:5]
        except Exception:
            pass

    context = str(node_def.get("context") or "") if isinstance(node_def, dict) else ""

    return {
        "event_id": canonical or scene_id or "unknown",
        "context": context,
        "characters": [{"name": name} for name in participants],
        "choices": [{"choice_id": c.get("choice_id", ""), "text": c.get("text", ""),
                      "target_event_id": c.get("target_event_id", ""), "tone": c.get("tone", "neutral")}
                     for c in (choices if isinstance(choices, list) else [])],
    }


def _read_session_state() -> dict[str, Any]:
    try:
        from engine import io_utils
        return io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        return {}


# ── Visual generation (narrative-node driven) ───────────────────────

def ensure_game_visuals(
    state: dict[str, Any],
    *,
    turn: int = 0,
    max_chars: int = 5,
    force: bool = False,
    background: bool = False,
) -> dict[str, Any]:
    """Generate/cache visuals for current game scene (convenience wrapper).

    Prefer ensure_game_visuals_from_node() when a narrative node is available.
    """
    scene_id = str(state.get("scene") or "").strip()
    node = resolve_game_narrative_node(scene_id)
    return ensure_game_visuals_from_node(node, turn=turn, max_chars=max_chars,
                                         force=force, background=background)


def ensure_game_visuals_from_node(
    node: dict[str, Any],
    *,
    turn: int = 0,
    max_chars: int = 5,
    force: bool = False,
    background: bool = False,
) -> dict[str, Any]:
    """Generate/cache visuals driven by a narrative node.

    Only generates visuals for characters that appear in this node (participants),
    not all characters in the world. Scene visual is keyed by node's event_id.

    Args:
        node: narrative node dict from resolve_game_narrative_node()
              {event_id, context, characters: [{name, ...}], choices}
        turn: current turn for registry tagging
        max_chars: max character portraits to generate
        force: ignore cache and regenerate
        background: fire-and-forget in daemon thread, return cached only
    """
    if not config.VISUAL_SYSTEM_ENABLED:
        return {"characters": [], "scene": None}

    char_names = [c.get("name", "") for c in node.get("characters", []) if c.get("name")]
    event_id = str(node.get("event_id") or "").strip()

    if background:
        _trigger_background_visuals_from_node(char_names, event_id, turn, max_chars, force)
        return _read_cached_visuals_from_node(char_names, event_id)

    return _generate_visuals_sync_from_node(char_names, event_id, turn, max_chars, force)


def _generate_visuals_sync_from_node(
    char_names: list[str],
    event_id: str,
    turn: int,
    max_chars: int,
    force: bool,
) -> dict[str, Any]:
    """Generate portraits + scene for a narrative node's participants."""
    from engine.visual.visual_runtime import get_visual

    result: dict[str, Any] = {"characters": [], "scene": None}

    for name in char_names[:max_chars]:
        try:
            visual = get_visual(
                "character", name,
                context={"scene": event_id, "turn": turn, "name": name},
                turn=turn, force=force,
            )
            if visual.get("image_path"):
                result["characters"].append({
                    "name": name,
                    "image_url": public_image_url(visual["image_path"]),
                })
        except Exception as exc:
            logger.debug("Game visual — skip character %s: %s", name, exc)

    if event_id:
        try:
            visual = get_visual(
                "event", event_id,
                context={"turn": turn},
                turn=turn, force=force,
            )
            if visual.get("image_path"):
                result["scene"] = {
                    "scene_id": event_id,
                    "image_url": public_image_url(visual["image_path"]),
                }
        except Exception as exc:
            logger.debug("Game visual — skip scene %s: %s", event_id, exc)

    return result


def _read_cached_visuals_from_node(
    char_names: list[str],
    event_id: str,
) -> dict[str, Any]:
    """Read existing visuals for node participants (no generation)."""
    from engine.visual.visual_registry import get_asset, list_assets, load_registry
    from pathlib import Path

    registry = load_registry()
    result: dict[str, Any] = {"characters": [], "scene": None}

    def _file_exists(image_path: str) -> bool:
        if not image_path:
            return False
        rel = str(image_path).replace("\\", "/")
        return (config.ROOT / rel).is_file()

    for name in char_names:
        asset = get_asset(registry, "characters", name)
        if not asset:
            for record in list_assets(registry, "characters").values():
                if isinstance(record, dict) and str(record.get("entity_id") or "") == name:
                    asset = record
                    break
        if not asset:
            for record in list_assets(registry, "characters").values():
                if isinstance(record, dict) and str(record.get("display_name") or "").strip() == str(name).strip():
                    asset = record
                    break
        image_path = str((asset or {}).get("image_path") or "")
        if isinstance(asset, dict) and image_path and _file_exists(image_path):
            result["characters"].append({
                "name": name,
                "image_url": public_image_url(image_path),
            })

    if event_id:
        asset = get_asset(registry, "events", event_id)
        image_path = str((asset or {}).get("image_path") or "")
        if asset and image_path and _file_exists(image_path):
            result["scene"] = {
                "scene_id": event_id,
                "image_url": public_image_url(image_path),
            }
        else:
            for record in list_assets(registry, "events").values():
                if isinstance(record, dict) and record.get("image_path"):
                    ip = str(record["image_path"])
                    if _file_exists(ip):
                        result["scene"] = {
                            "scene_id": str(record.get("entity_id") or record.get("asset_id") or ""),
                            "image_url": public_image_url(ip),
                        }
                        break

    return result


def _trigger_background_visuals_from_node(
    char_names: list[str],
    event_id: str,
    turn: int,
    max_chars: int,
    force: bool,
) -> None:
    def _work():
        try:
            _generate_visuals_sync_from_node(char_names, event_id, turn, max_chars, force)
        except Exception as exc:
            logger.warning("Background visual generation failed: %s", exc)
    t = threading.Thread(target=_work, daemon=True)
    t.start()


# ── Legacy helpers (keep backward compat) ───────────────────────────

def read_all_character_visuals() -> list[dict[str, str]]:
    """Read ALL character visuals from registry — for Game right-panel HUB.

    Returns a list of {name, image_url} for every character that has a
    generated portrait on disk.  Unlike ensure_game_visuals_from_node(),
    this is NOT tied to a narrative node — it serves the always-visible
    character roster in the game sidebar.
    """
    if not config.VISUAL_SYSTEM_ENABLED:
        return []
    from engine.visual.visual_registry import list_assets, load_registry

    registry = load_registry()
    seen: set[str] = set()
    result: list[dict[str, str]] = []

    for asset_id, record in list_assets(registry, "characters").items():
        if not isinstance(record, dict):
            continue
        image_path = str(record.get("image_path") or "").strip()
        name = str(record.get("entity_id") or record.get("display_name") or asset_id).strip()
        if not image_path or not name or name in seen:
            continue
        rel = image_path.replace("\\", "/")
        if not (config.ROOT / rel).is_file():
            continue
        seen.add(name)
        result.append({"name": name, "image_url": public_image_url(image_path)})
    return result


def read_all_faction_visuals() -> list[dict[str, str]]:
    """Read ALL faction visuals from registry — for Game right-panel HUB.

    Returns a list of {name, image_url} for every faction that has a
    generated emblem/banner on disk.
    """
    if not config.VISUAL_SYSTEM_ENABLED:
        return []
    from engine.visual.visual_registry import list_assets, load_registry

    registry = load_registry()
    seen: set[str] = set()
    result: list[dict[str, str]] = []

    for asset_id, record in list_assets(registry, "factions").items():
        if not isinstance(record, dict):
            continue
        image_path = str(record.get("image_path") or "").strip()
        name = str(record.get("entity_id") or record.get("display_name") or asset_id).strip()
        if not image_path or not name or name in seen:
            continue
        rel = image_path.replace("\\", "/")
        if not (config.ROOT / rel).is_file():
            continue
        seen.add(name)
        result.append({"name": name, "image_url": public_image_url(image_path)})
    return result


def _generate_faction_visuals_sync(world_pack: dict, turn: int) -> list[dict[str, str]]:
    """Generate emblems for all factions in world_pack — sync blocking call."""
    from engine.visual.visual_runtime import get_visual

    result = []
    factions = world_pack.get("world", {}).get("factions", [])
    for faction in factions:
        name = faction.get("name", "")
        if not name:
            continue
        try:
            visual = get_visual(
                "faction", name,
                context={"turn": turn, "name": name,
                         "type": faction.get("type", ""),
                         "description": faction.get("description", "")},
                turn=turn, force=False,
            )
            if visual.get("image_path"):
                result.append({
                    "name": name,
                    "image_url": public_image_url(visual["image_path"]),
                })
        except Exception:
            pass
    return result


def _trigger_background_faction_visuals(world_pack: dict, turn: int) -> None:
    """Fire-and-forget faction emblem generation in daemon thread."""

    def _work():
        try:
            _generate_faction_visuals_sync(world_pack, turn)
        except Exception as exc:
            logger.warning("Background faction emblem generation failed: %s", exc)

    t = threading.Thread(target=_work, daemon=True)
    t.start()


# Guard: only trigger faction generation once per boot (module cache)
_faction_visuals_triggered: bool = False


def bootstrap_game_visuals(node_visuals: dict[str, Any]) -> dict[str, Any]:
    """Merge node-visuals with ALL character & faction visuals for the game sidebar HUB.

    node_visuals = output of ensure_game_visuals_from_node()  {characters, scene}
    Returns the same shape + ``factions``, with every character/faction that
    has a visual on disk.  Node participants always take precedence.

    Side effect: when zero faction visuals exist on disk and world_pack has
    factions configured, a background thread is spawned once to generate
    emblems for every faction.
    """
    global _faction_visuals_triggered

    all_chars = read_all_character_visuals()
    char_map: dict[str, dict[str, str]] = {}
    for c in all_chars:
        char_map[c["name"]] = c
    for c in node_visuals.get("characters", []):
        char_map[c["name"]] = c

    all_factions = read_all_faction_visuals()
    faction_map: dict[str, dict[str, str]] = {}
    for f in all_factions:
        faction_map[f["name"]] = f
    for f in node_visuals.get("factions", []):
        faction_map[f["name"]] = f

    # ── Auto-generate faction emblems in background if missing ──
    if not faction_map and not _faction_visuals_triggered and config.VISUAL_SYSTEM_ENABLED:
        _faction_visuals_triggered = True
        from engine import io_utils

        wp = io_utils.read_yaml(config.WORLD_PACK_PATH)
        wp_factions = wp.get("world", {}).get("factions", [])
        if wp_factions:
            logger.info("Bootstrapping faction emblem generation (%d factions)", len(wp_factions))
            _trigger_background_faction_visuals(wp, turn=0)

    return {
        "characters": list(char_map.values()),
        "factions": list(faction_map.values()),
        "scene": node_visuals.get("scene"),
    }


def _ranked_characters(characters_raw: dict) -> list[dict[str, str]]:
    entries = []
    for key, ch in characters_raw.items():
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name") or key).strip()
        if not name:
            continue
        is_main = ch.get("is_main") or ch.get("isMain") or False
        entries.append({"name": name, "is_main": is_main})
    entries.sort(key=lambda x: (not x["is_main"], x["name"]))
    return entries


def _read_cached_visuals(characters_raw: dict, scene_id: str) -> dict[str, Any]:
    char_names = [e["name"] for e in _ranked_characters(characters_raw)]
    return _read_cached_visuals_from_node(char_names, scene_id)


# ── Game frame builder ──────────────────────────────────────────────

def build_game_frame(
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    background_visuals: bool = True,
) -> dict[str, Any]:
    """Wire step() result + narrative node + visuals into a complete game frame."""
    turn = state.get("turn", result.get("turn", 0))
    scene_id = str(state.get("scene") or "").strip()
    node = resolve_game_narrative_node(scene_id)
    visuals = ensure_game_visuals_from_node(
        node, turn=turn, force=False, background=background_visuals,
    )
    return {
        **result,
        "visuals": visuals,
        "narrative_node": node,
    }


# ── Story-based illustration generation ─────────────────────────────

def generate_story_illustration(
    story_text: str,
    scene_id: str | None = None,
    *,
    turn: int = 0,
    sync: bool = True,
) -> dict[str, Any] | None:
    """Generate an illustration summarising the story chapter just written.

    1.  Ask DeepSeek to convert the story passage into a concise English
        image-generation prompt (250 chars max), informed by world character
        appearances.
    2.  Generate the image via the configured visual provider (e.g. Agnes).
    3.  Save it to the filesystem cache and register it.

    Returns ``{scene_id, image_url}`` or ``None`` on any failure so the
    caller can safely fall back to the pre-existing scene visual.
    """
    if not config.VISUAL_SYSTEM_ENABLED or not story_text.strip():
        return None

    # ── 1. Story → visual prompt (DeepSeek, character-aware) ─────────
    visual_prompt = _story_to_visual_prompt(story_text)
    if not visual_prompt:
        return None

    # ── 2. Prompt → image (visual provider) ─────────────────────────
    if not sync:
        _trigger_background_illustration(visual_prompt, scene_id, turn)
        return None  # will appear on next turn via registry cache

    return _generate_illustration_sync(visual_prompt, scene_id, turn)


def _story_to_visual_prompt(story_text: str) -> str:
    """Use DeepSeek to first summarise the story, then generate an image prompt.

    Two-phase in one call:
      1. Summarise the full chapter: key scene, characters, mood, turning point
      2. Convert that summary into an English Stable‑Diffusion prompt

    Also injects character appearance descriptions from world_pack so
    generated artwork stays visually consistent with the world's character
    designs.
    """
    from engine.deepseek_client import call_deepseek, DeepSeekError
    from engine import io_utils

    # Feed enough of the story for meaningful summarisation
    truncated = story_text[:4000].strip()
    if len(story_text) > 4000:
        truncated += "…"

    # ── Inject character appearance context ──────────────────────────
    character_notes = ""
    try:
        wp = io_utils.read_yaml(config.WORLD_PACK_PATH)
        chars = wp.get("world", {}).get("characters", [])
        if isinstance(chars, list):
            lines = []
            for ch in chars[:8]:
                name = str(ch.get("name") or "").strip()
                appearance = str(ch.get("appearance") or "").strip()
                if name and appearance:
                    lines.append(f"- {name}：{appearance}")
            if lines:
                character_notes = (
                    "\n\n【角色外貌设定——绘图prompt必须严格遵循以下外观描述】\n"
                    + "\n".join(lines)
                    + "\n生成的prompt中角色外貌必须与上述设定完全一致。"
                )
    except Exception:
        pass

    system = (
        "你是一个为小说配图的AI画师。请严格按以下两步工作：\n\n"
        "第一步：仔细阅读下面的小说正文，用中文写一段100字以内的概括，"
        "必须包含：当前场景地点、有哪些角色在场、正在发生什么关键事件、"
        "整体情绪/氛围。\n\n"
        "第二步：基于你上一步的概括，生成一段适合AI绘图模型的英文prompt。"
        + character_notes + "\n\n"
        "只输出一个 JSON 对象：{\"summary\": \"你的中文概括\", \"prompt\": \"英文绘图prompt\"}\n"
        "prompt 必须为英文，控制在250词以内。不要输出任何解释性文字。"
    )

    try:
        response = call_deepseek(
            system, truncated,
            max_tokens=600,
            temperature=0.6,
            skip_validation=True,
        )
        if isinstance(response, dict):
            summary = str(response.get("summary") or "").strip()
            prompt_text = str(response.get("prompt") or "").strip()
            if summary:
                logger.info("Story illustration summary: %s", summary[:120])
            if prompt_text:
                return prompt_text[:500]
    except DeepSeekError as exc:
        logger.warning("Story→visual prompt generation failed: %s", exc)
    return ""


def _generate_illustration_sync(
    visual_prompt: str,
    scene_id: str | None,
    turn: int,
) -> dict[str, Any] | None:
    """Generate the illustration image and register it."""
    from engine.visual.provider_factory import get_visual_provider
    from engine.visual.visual_cache import uri_for_path, write_bytes
    from engine.visual.visual_registry import (
        entity_type_to_scope,
        kind_for_entity_type,
        load_registry,
        make_asset_record,
        save_registry,
        set_asset,
    )

    sid = str(scene_id or f"turn_{turn}").strip()
    scope = entity_type_to_scope("event")
    asset_id = f"story_illustration_{sid}_t{turn}"

    provider = get_visual_provider()
    max_retries = max(1, int(getattr(config, "VISUAL_MAX_RETRIES", 3) or 3))

    data = None
    for attempt in range(max_retries):
        try:
            data = provider.generate_event(
                prompt=visual_prompt,
                asset_id=asset_id,
                size="680x220",
            )
            break
        except Exception as exc:
            if attempt < max_retries - 1:
                logger.warning("Illustration gen attempt %d/%d failed: %s",
                               attempt + 1, max_retries, exc)
                import time
                time.sleep(0.2 * (2 ** attempt))
            else:
                logger.error("Illustration gen failed after %d attempts", max_retries)
                return None

    if not data:
        return None

    try:
        path = write_bytes(scope, asset_id, data)
        image_path = uri_for_path(path)
    except Exception as exc:
        logger.error("Failed to save illustration: %s", exc)
        return None

    # Register
    try:
        registry = load_registry()
        record = make_asset_record(
            asset_id=asset_id,
            display_name=f"Turn {turn} illustration",
            image_path=image_path,
            entity_id=f"story_t{turn}",
            entity_type="event",
            provider=provider.provider_name,
            kind=kind_for_entity_type("event"),
            created_turn=turn,
        )
        registry = set_asset(registry, scope, asset_id, record)
        save_registry(registry)
    except Exception as exc:
        logger.warning("Illustration registry save failed (image still on disk): %s", exc)

    return {
        "scene_id": f"story_t{turn}",
        "image_url": public_image_url(image_path),
    }


def _trigger_background_illustration(
    visual_prompt: str,
    scene_id: str | None,
    turn: int,
) -> None:
    def _work():
        try:
            _generate_illustration_sync(visual_prompt, scene_id, turn)
        except Exception as exc:
            logger.warning("Background illustration generation failed: %s", exc)
    t = threading.Thread(target=_work, daemon=True)
    t.start()

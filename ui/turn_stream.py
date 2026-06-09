"""SSE streaming helpers for game turn endpoints (/api/next, /api/start)."""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi.responses import JSONResponse, StreamingResponse

import config
from engine import io_utils
from engine.generation_control import clear_cancel, request_cancel
from engine.memory import load_memory, get_faction_stats_for_ui
from engine.run import get_last_step_error, step
from engine.save_manager import load_runtime_memory

logger = logging.getLogger("api")

_active_workers = 0


def build_turn_payload(result: dict, *, force_sync_visuals: bool = False) -> dict[str, Any]:
    """Merge step() result with session/memory for frontend.

    When *force_sync_visuals* is True (opening turn), visual generation runs
    synchronously so the first response already carries portraits/emblems/scene.
    """
    from ui.routes.api import _merge_characters_with_memory
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    memory = load_memory()
    mem_chars = memory.get("characters", {})
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_chars = world_pack.get("world", {}).get("characters", [])
        faction_map = {
            wc["name"]: wc.get("faction", "")
            for wc in world_chars
            if "name" in wc
        }
    except Exception:
        faction_map = {}

    chars_with_trust = _merge_characters_with_memory(
        state.get("characters", {}),
        mem_chars,
        faction_map,
    )

    factions_data: list[dict] = []
    try:
        factions_data = get_faction_stats_for_ui(memory)
    except Exception:
        pass

    # ── V6 Game Runtime: narrative node → visuals ──
    from engine.game_runtime import resolve_game_narrative_node, ensure_game_visuals_from_node, bootstrap_game_visuals

    scene_id = str(state.get("scene") or "").strip()
    node = resolve_game_narrative_node(scene_id)
    visuals = ensure_game_visuals_from_node(node, turn=state.get("turn", 0), background=not force_sync_visuals)
    visuals = bootstrap_game_visuals(visuals)

    logger.info("[VISUAL] scene=%s scene_visual=%s chapter=%s turn=%s",
                scene_id,
                (visuals.get("scene") or {}).get("scene_id", "none"),
                state.get("chapter", "?"),
                state.get("turn", "?"))

    # ── Story-based illustration: replace scene visual with actual chapter art ──
    story_text = result.get("story", "")
    if story_text.strip():
        from engine.game_runtime import generate_story_illustration
        turn = state.get("turn", 0) or result.get("turn", 0)
        story_ill = generate_story_illustration(
            story_text,
            scene_id=scene_id,
            turn=turn,
            sync=not force_sync_visuals,  # sync on regular turns, async on opening
        )
        if story_ill:
            visuals["scene"] = story_ill
            logger.info("[VISUAL] illustration generated — scene=%s image=%s",
                        scene_id, story_ill.get("image_url", "?")[-40:])

    # ── Visual consistency audit ──
    story_text = result.get("story", "")
    story_lower = (story_text or "").lower()
    scene_lower = scene_id.lower()
    story_match = scene_lower in story_lower or any(w in story_lower for w in scene_lower.split()) if scene_lower else False
    node_chars = [c.get("name", "") for c in node.get("characters", [])]
    char_match = all(name.lower() in story_lower for name in node_chars) if node_chars else True
    logger.info("[VISUAL_AUDIT] scene=%s chapter=%s visual=%s story_match=%s character_match=%s",
                scene_id,
                state.get("chapter", "?"),
                (visuals.get("scene") or {}).get("scene_id", "none"),
                story_match,
                char_match)

    from ui.routes.api import _objectives_for_game
    return {
        "story": result.get("story", ""),
        "options": result.get("options", []),
        "state": {
            "turn": state.get("turn", result.get("turn", 0)),
            "status": state.get("status", result.get("status", "SETUP")),
            "scene": state.get("scene", result.get("scene", "")),
            "characters": chars_with_trust,
            "factions": factions_data,
            "objectives": _objectives_for_game(state),
            "force_event_pending": state.get("force_event_pending", False),
            "chapter": state.get("chapter", 1),
        },
        "visuals": visuals,
        "narrative_node": node,
    }


def cancel_active_generation() -> dict[str, bool]:
    """Signal the in-flight worker to stop after current API call."""
    from engine.save_manager import clear_runtime_memory

    request_cancel()
    if _active_workers == 0:
        clear_runtime_memory()
    return {"cancelled": True}


def get_generation_status() -> dict[str, Any]:
    """Return partial in-flight story for disconnect recovery."""
    partial = load_runtime_memory() or {}
    story = partial.get("story", "")
    in_process = _active_workers > 0
    if in_process:
        return {
            "active": True,
            "story": story,
            "cancelled": bool(partial.get("cancelled")),
        }
    if partial.get("active") is True and story:
        return {"active": False, "story": story, "stale": True}
    return {
        "active": False,
        "story": story,
        "cancelled": bool(partial.get("cancelled")),
    }


def run_step_sync(
    choice: str | None,
    event_queue: queue.Queue,
) -> dict | None:
    """Run step() in worker thread, pushing SSE events to *event_queue*."""
    global _active_workers
    clear_cancel()
    _active_workers += 1

    def on_story_delta(delta: str) -> None:
        event_queue.put({"type": "story", "delta": delta})
        try:
            from engine.generation_control import get_partial_story
            from engine.save_manager import save_runtime_memory
            save_runtime_memory({"story": get_partial_story(), "active": True})
        except Exception:
            pass

    def on_story_reset() -> None:
        event_queue.put({"type": "story_reset"})

    def on_progress(phase: str, extra: dict) -> None:
        event_queue.put({"type": "progress", "phase": phase, **extra})

    result = None
    try:
        result = step(
            choice,
            on_story_delta=on_story_delta,
            on_story_reset=on_story_reset,
            on_progress=on_progress,
        )
    except Exception:
        logger.error("step() failed", exc_info=True)
        from engine.save_manager import clear_runtime_memory
        clear_runtime_memory()
        event_queue.put({
            "type": "error",
            "error": get_last_step_error() or "AI 生成失败，请重试",
        })
        return None
    finally:
        _active_workers -= 1

    if result is None:
        from engine.save_manager import clear_runtime_memory
        clear_runtime_memory()
        err = get_last_step_error() or "AI 生成失败，请重试"
        event_queue.put({"type": "error", "error": err})
        return None

    event_queue.put({"type": "done", "result": result})
    return result


async def stream_turn_events(
    choice: str | None,
    *,
    build_payload: Callable[[dict], dict[str, Any]] | None = None,
    force_sync_visuals: bool = False,
) -> AsyncIterator[str]:
    """Async generator yielding SSE frames for one game turn."""
    event_queue: queue.Queue = queue.Queue()
    payload_fn = build_payload or (lambda r: build_turn_payload(r, force_sync_visuals=force_sync_visuals))

    worker = threading.Thread(
        target=run_step_sync,
        args=(choice, event_queue),
        daemon=True,
    )
    worker.start()

    loop = asyncio.get_running_loop()
    while True:
        item = await loop.run_in_executor(None, event_queue.get)
        kind = item.get("type")

        if kind == "story":
            yield _sse("story", {"delta": item["delta"]})
        elif kind == "story_reset":
            yield _sse("story_reset", {})
        elif kind == "progress":
            payload = {k: v for k, v in item.items() if k != "type"}
            yield _sse("progress", payload)
        elif kind == "error":
            yield _sse("error", {"error": item.get("error", "AI 生成失败，请重试")})
            break
        elif kind == "done":
            payload = payload_fn(item["result"])
            yield _sse("done", payload)
            break

    await loop.run_in_executor(None, worker.join)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def turn_response(choice: str | None, *, opening: bool = False):
    """
    Return JSON or SSE response for a turn, depending on config.STREAM.
    *opening* tweaks default turn in payload when session read fails.
    """
    config.reload_stream()

    if not config.DEEPSEEK_API_KEY:
        return JSONResponse(
            {"error": "未配置 DeepSeek API Key，请先在设置页填写"},
            status_code=400,
        )

    if config.STREAM:
        async def generate():
            async for frame in stream_turn_events(choice, force_sync_visuals=opening):
                yield frame

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    result = step(choice)
    if result is None:
        err = get_last_step_error() or "AI 生成失败，请重试"
        return JSONResponse({"error": err}, status_code=500)

    payload = build_turn_payload(result, force_sync_visuals=opening)
    if opening and payload["state"].get("turn") in (0, None):
        payload["state"]["turn"] = result.get("turn", 1)
        payload["state"]["force_event_pending"] = False
    return JSONResponse(payload)

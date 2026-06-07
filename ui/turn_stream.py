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


def build_turn_payload(result: dict) -> dict[str, Any]:
    """Merge step() result with session/memory for frontend."""
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

    return {
        "story": result.get("story", ""),
        "options": result.get("options", []),
        "state": {
            "turn": state.get("turn", result.get("turn", 0)),
            "status": state.get("status", result.get("status", "SETUP")),
            "scene": state.get("scene", result.get("scene", "")),
            "characters": chars_with_trust,
            "factions": factions_data,
            "force_event_pending": state.get("force_event_pending", False),
            "chapter": state.get("chapter", 1),
        },
    }


def cancel_active_generation() -> dict[str, bool]:
    """Signal the in-flight worker to stop after current API call."""
    request_cancel()
    return {"cancelled": True}


def get_generation_status() -> dict[str, Any]:
    """Return partial in-flight story for disconnect recovery."""
    partial = load_runtime_memory()
    if not partial:
        return {"active": False, "story": ""}
    return {
        "active": bool(partial.get("story")),
        "story": partial.get("story", ""),
        "cancelled": bool(partial.get("cancelled")),
    }


def run_step_sync(
    choice: str | None,
    event_queue: queue.Queue,
) -> dict | None:
    """Run step() in worker thread, pushing SSE events to *event_queue*."""
    clear_cancel()

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

    try:
        result = step(
            choice,
            on_story_delta=on_story_delta,
            on_story_reset=on_story_reset,
            on_progress=on_progress,
        )
    except Exception:
        logger.error("step() failed", exc_info=True)
        event_queue.put({
            "type": "error",
            "error": get_last_step_error() or "AI 生成失败，请重试",
        })
        return None

    if result is None:
        err = get_last_step_error() or "AI 生成失败，请重试"
        event_queue.put({"type": "error", "error": err})
        return None

    event_queue.put({"type": "done", "result": result})
    return result


async def stream_turn_events(
    choice: str | None,
    *,
    build_payload: Callable[[dict], dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    """Async generator yielding SSE frames for one game turn."""
    event_queue: queue.Queue = queue.Queue()
    payload_fn = build_payload or build_turn_payload

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
            async for frame in stream_turn_events(choice):
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

    payload = build_turn_payload(result)
    if opening and payload["state"].get("turn") in (0, None):
        payload["state"]["turn"] = result.get("turn", 1)
        payload["state"]["force_event_pending"] = False
    return JSONResponse(payload)

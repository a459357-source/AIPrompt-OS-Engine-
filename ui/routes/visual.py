"""Read-only Visual World API for V6.5 UI."""

from fastapi import APIRouter

from engine.visual.visual_api import (
    get_character_gallery,
    get_event_timeline,
    get_visual_debug_payload,
    get_visual_status,
    get_world_explorer,
)

router = APIRouter(prefix="/api/visual", tags=["visual"])


@router.get("/status")
async def visual_status():
    return get_visual_status()


@router.get("/gallery/characters")
async def visual_character_gallery():
    return {"characters": get_character_gallery()}


@router.get("/world")
async def visual_world():
    return get_world_explorer()


@router.get("/events")
async def visual_events():
    return {"events": get_event_timeline()}


@router.get("/debug")
async def visual_debug():
    return get_visual_debug_payload()

"""V6.6 Narrative Entry Layer API — routing and display only."""

from fastapi import APIRouter, Form

from engine.narrative.narrative_entry import build_narrative_node, get_narrative_hub
from engine.narrative.narrative_router import (
    resolve_character_entry,
    resolve_location_entry,
    resolve_visual_event_entry,
)
from engine.narrative.narrative_router import get_choices_for_event, route_choice
from engine.narrative.narrative_state import (
    enter_narrative_node,
    load_narrative_state,
    record_choice,
    set_narrative_mode,
)
from engine.narrative.visual_continuity import build_continuity_hints

router = APIRouter(prefix="/api/narrative", tags=["narrative"])


@router.get("/state")
async def narrative_state():
    return load_narrative_state()


@router.post("/mode")
async def narrative_mode(mode: str = Form(...)):
    return set_narrative_mode(mode)


@router.get("/hub")
async def narrative_hub():
    return get_narrative_hub()


@router.get("/node/{event_id}")
async def narrative_node(event_id: str):
    return build_narrative_node(event_id)


@router.get("/choices/{event_id}")
async def narrative_choices(event_id: str):
    from engine.narrative.narrative_router import resolve_canonical_event_id

    canonical = resolve_canonical_event_id(event_id)
    return {"event_id": canonical, "choices": get_choices_for_event(canonical)}


@router.post("/route")
async def narrative_route(
    event_id: str = Form(...),
    choice_id: str = Form(...),
):
    result = route_choice(event_id, choice_id)
    if not result.get("ok"):
        return result

    next_id = str(result["next_event_id"])
    prev_id = str(result["event_id"])
    node = build_narrative_node(next_id)
    continuity = build_continuity_hints(
        event_id=next_id,
        characters=[c["name"] for c in node.get("characters") or []],
        previous_event_id=prev_id,
    )
    record_choice(event_id=prev_id, choice_id=choice_id, next_event_id=next_id)
    enter_narrative_node(next_id, entry_type="choice", continuity=continuity)

    return {
        **result,
        "node": node,
        "continuity": continuity,
    }


@router.post("/enter/event")
async def enter_from_event(event_id: str = Form(...)):
    narrative_id = resolve_visual_event_entry(event_id)
    node = build_narrative_node(narrative_id, visual_event_id=event_id)
    enter_narrative_node(narrative_id, entry_type="event", continuity=node.get("continuity") or {})
    return {"narrative_event_id": narrative_id, "node": node}


@router.post("/enter/character")
async def enter_from_character(character_name: str = Form(...)):
    narrative_id = resolve_character_entry(character_name)
    node = build_narrative_node(narrative_id)
    enter_narrative_node(narrative_id, entry_type="character", continuity=node.get("continuity") or {})
    return {"narrative_event_id": narrative_id, "node": node}


@router.post("/enter/location")
async def enter_from_location(location_name: str = Form(...)):
    narrative_id = resolve_location_entry(location_name)
    node = build_narrative_node(narrative_id)
    enter_narrative_node(narrative_id, entry_type="location", continuity=node.get("continuity") or {})
    return {"narrative_event_id": narrative_id, "node": node}

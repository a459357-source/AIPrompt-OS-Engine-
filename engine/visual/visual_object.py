"""
visual_object.py — V6.1 VisualObject (identity-aware)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from engine.visual.identity_prompt_builder import build_identity_prompt
from engine.visual.identity_registry import resolve_identity
from engine.visual.prompt_canonical import normalize_prompt
from engine.visual.visual_cache import canonical_prompt_hash, idempotency_key, identity_idempotency_key
from engine.visual.visual_identity import VisualIdentity
from engine.visual.visual_registry import ENTITY_TYPES, normalize_asset_id

_PROVIDER_METHOD = {
    "character": "generate_character",
    "location": "generate_location",
    "faction": "generate_faction",
    "event": "generate_event",
}

_DEFAULT_SIZE = {
    "character": "1024x1024",
    "location": "1536x1024",
    "faction": "1536x1024",
    "event": "1024x1024",
}


@dataclass
class VisualObject:
    entity_type: str
    entity_id: str
    identity_id: str
    seed: int
    name: str
    description: str
    context_tags: list[str] = field(default_factory=list)
    prompt: str = ""
    prompt_hash: str = ""
    asset_id: str = ""
    idempotency_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def provider_method(self) -> str:
        return _PROVIDER_METHOD[self.entity_type]

    @property
    def default_size(self) -> str:
        return _DEFAULT_SIZE[self.entity_type]


def build_visual_object(
    entity_type: str,
    entity_id: str,
    context: dict | None = None,
) -> VisualObject:
    """entity_id → identity → prompt → VisualObject."""
    et = str(entity_type or "").strip().lower()
    if et not in ENTITY_TYPES:
        raise ValueError(f"invalid entity_type: {entity_type!r}; allowed: {sorted(ENTITY_TYPES)}")

    ctx = context if isinstance(context, dict) else {}
    eid = str(entity_id or "").strip() or "unknown"
    identity = resolve_identity(et, eid, ctx)
    name = str(ctx.get("name") or eid).strip()
    description = str(ctx.get("description") or "").strip()
    tags = [str(t) for t in (ctx.get("context_tags") or ctx.get("tags") or []) if str(t).strip()]

    raw_prompt = build_identity_prompt(identity, ctx)
    canonical = normalize_prompt(raw_prompt)
    phash = canonical_prompt_hash(canonical)
    asset_id = str(ctx.get("asset_id") or "").strip() or _default_asset_id(et, eid, ctx)
    ikey = _idempotency_for(identity, et, eid, phash)

    return VisualObject(
        entity_type=et,
        entity_id=eid,
        identity_id=identity.identity_id,
        seed=identity.seed,
        name=name,
        description=description,
        context_tags=tags,
        prompt=canonical,
        prompt_hash=phash,
        asset_id=asset_id,
        idempotency_key=ikey,
    )


def _idempotency_for(identity: VisualIdentity, entity_type: str, entity_id: str, prompt_hash: str) -> str:
    if entity_type == "character":
        return identity_idempotency_key(identity.identity_id, entity_type)
    return idempotency_key(entity_type, entity_id, prompt_hash)


def _default_asset_id(entity_type: str, entity_id: str, ctx: dict) -> str:
    if entity_type == "location":
        world = ctx.get("world_pack") or {}
        w = world.get("world", world) if isinstance(world, dict) else {}
        title = str(w.get("title") or w.get("name") or entity_id)
        return normalize_asset_id(title) + "_map"
    if entity_type == "faction":
        return normalize_asset_id(entity_id) + "_territory"
    return normalize_asset_id(entity_id)

"""
visual_identity.py — V6.1 VisualIdentity core model
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VisualIdentity:
    """Stable visual anchor for a narrative entity."""

    identity_id: str
    entity_type: str
    entity_id: str
    canonical_traits: dict[str, Any] = field(default_factory=dict)
    style_anchor: dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    locked_descriptors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict | None) -> VisualIdentity | None:
        if not isinstance(raw, dict):
            return None
        identity_id = str(raw.get("identity_id") or "").strip()
        entity_type = str(raw.get("entity_type") or "").strip().lower()
        entity_id = str(raw.get("entity_id") or "").strip()
        if not identity_id or not entity_type or not entity_id:
            return None
        traits = raw.get("canonical_traits")
        anchor = raw.get("style_anchor")
        locked = raw.get("locked_descriptors")
        return cls(
            identity_id=identity_id,
            entity_type=entity_type,
            entity_id=entity_id,
            canonical_traits=traits if isinstance(traits, dict) else {},
            style_anchor=anchor if isinstance(anchor, dict) else {},
            seed=int(raw.get("seed") or 0),
            locked_descriptors=[str(x) for x in locked if str(x).strip()] if isinstance(locked, list) else [],
        )


def make_identity_id(entity_type: str, entity_id: str) -> str:
    raw = f"{entity_type}:{entity_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return f"vid_{digest}"


def seed_from_identity_id(identity_id: str) -> int:
    digest = hashlib.sha256(identity_id.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16) % (2**31 - 1)


def entity_lookup_key(entity_type: str, entity_id: str) -> str:
    return f"{str(entity_type).strip().lower()}:{str(entity_id).strip()}"

"""Content Template System — IP worldbuilding constraint layer (V6 add-on)."""

from engine.templates.style_bible import apply_style_bible, reinforce_style_bible, style_tokens_for_entity
from engine.templates.template_prompt import build_prompt_from_template
from engine.templates.template_resolver import resolve_content_template
from engine.templates.world_content_pack import (
    apply_dataset_import,
    build_entity_prompt,
    build_full_dataset_prompt,
    validate_world_dataset,
)

__all__ = [
    "resolve_content_template",
    "build_prompt_from_template",
    "apply_style_bible",
    "reinforce_style_bible",
    "style_tokens_for_entity",
    "build_entity_prompt",
    "build_full_dataset_prompt",
    "validate_world_dataset",
    "apply_dataset_import",
]

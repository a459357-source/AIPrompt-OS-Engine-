"""Content Template System — IP worldbuilding constraint layer (V6 add-on)."""

from engine.templates.template_prompt import build_prompt_from_template
from engine.templates.template_resolver import resolve_content_template

__all__ = ["resolve_content_template", "build_prompt_from_template"]

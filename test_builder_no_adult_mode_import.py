"""Static checks for unified prompt builder (no direct ADULT_MODE reads)."""
from pathlib import Path


def test_builder_does_not_reference_adult_mode():
    text = Path("engine/builder.py").read_text(encoding="utf-8")
    assert "ADULT_MODE" not in text
    assert "adult_mode" not in text
    assert "resolve_prompt_template_path" not in text.split("_build_prompt_unified")[0]

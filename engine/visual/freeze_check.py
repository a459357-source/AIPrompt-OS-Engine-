"""
freeze_check.py — V6 Freeze Checklist automated architecture lock checks
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VISUAL_DIR = ROOT / "engine" / "visual"
TEMPLATES_DIR = ROOT / "engine" / "templates"
UI_VISUAL_ROUTE = ROOT / "ui" / "routes" / "visual.py"

_FORBIDDEN_VISUAL_MODULES = (
    "memory_graph",
    "visual_evolution",
    "visual_simulation",
    "style_ml",
    "cv_drift",
)

_REGISTRY_REQUIRED_FIELDS = frozenset({
    "asset_id",
    "entity_type",
    "entity_id",
    "identity_id",
    "display_name",
    "prompt_hash",
    "image_path",
    "provider",
    "kind",
    "created_turn",
    "created_at",
    "meta",
})


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_single_get_visual_entry() -> list[str]:
    errors: list[str] = []
    runtime = VISUAL_DIR / "visual_runtime.py"
    if not runtime.is_file():
        return ["missing visual_runtime.py"]
    text = _read(runtime)
    count = len(re.findall(r"^def get_visual\(", text, flags=re.MULTILINE))
    if count != 1:
        errors.append(f"get_visual() entry points in visual_runtime.py: expected 1, got {count}")
    return errors


def check_no_visual_context_imports() -> list[str]:
    errors: list[str] = []
    legacy = VISUAL_DIR / "visual_context.py"
    for path in (ROOT / "engine").rglob("*.py"):
        if path == legacy:
            continue
        if path.name == "freeze_check.py":
            continue
        text = _read(path)
        if "visual_context" in text and (
            "from engine.visual.visual_context" in text
            or "import visual_context" in text
        ):
            errors.append(f"forbidden visual_context import: {path.relative_to(ROOT)}")
    return errors


def check_forbidden_visual_modules() -> list[str]:
    errors: list[str] = []
    if not VISUAL_DIR.is_dir():
        return errors
    for path in VISUAL_DIR.glob("*.py"):
        stem = path.stem.lower()
        for forbidden in _FORBIDDEN_VISUAL_MODULES:
            if forbidden in stem:
                errors.append(f"forbidden visual module file: {path.name}")
    return errors


def check_provider_no_registry_writes() -> list[str]:
    errors: list[str] = []
    for name in ("visual_provider.py", "agnes_visual_provider.py", "image_generation.py"):
        path = VISUAL_DIR / name
        if not path.is_file():
            continue
        text = _read(path)
        if "save_registry" in text or "set_asset(" in text:
            errors.append(f"provider/generation must not write registry: {name}")
    return errors


def check_visual_api_read_only() -> list[str]:
    errors: list[str] = []
    if not UI_VISUAL_ROUTE.is_file():
        return ["missing ui/routes/visual.py"]
    text = _read(UI_VISUAL_ROUTE)
    if re.search(r"@router\.(post|put|patch|delete)\(", text, flags=re.IGNORECASE):
        errors.append("ui/routes/visual.py must be GET-only (read-only API)")
    return errors


def check_pipeline_integrity() -> list[str]:
    """Drift + governance must stay wired in visual_runtime."""
    errors: list[str] = []
    runtime = VISUAL_DIR / "visual_runtime.py"
    text = _read(runtime)
    required_calls = (
        "_generate_with_drift_policy",
        "_apply_quality_governance",
        "evaluate_generation",
        "evaluate_quality",
    )
    for token in required_calls:
        if token not in text:
            errors.append(f"visual_runtime missing pipeline hook: {token}")
    if "_generate_with_drift_policy" not in text or "save_registry" not in text:
        errors.append("get_visual must route generation through drift policy before registry")
    return errors


def check_identity_prompt_builder_only() -> list[str]:
    errors: list[str] = []
    vo = VISUAL_DIR / "visual_object.py"
    text = _read(vo)
    if "identity_prompt_builder" not in text:
        errors.append("visual_object must use identity_prompt_builder")
    if "visual_context" in text:
        errors.append("visual_object must not import visual_context")
    return errors


def check_registry_schema_stable() -> list[str]:
    errors: list[str] = []
    reg = VISUAL_DIR / "visual_registry.py"
    tree = ast.parse(_read(reg))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "make_asset_record":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                if child.value in _REGISTRY_REQUIRED_FIELDS:
                    found.add(child.value)
    missing = _REGISTRY_REQUIRED_FIELDS - found
    if missing:
        errors.append(f"make_asset_record missing frozen fields: {sorted(missing)}")
    return errors


def check_style_bible_single_engine_entry() -> list[str]:
    errors: list[str] = []
    builder = VISUAL_DIR / "identity_prompt_builder.py"
    text = _read(builder)
    if "apply_style_bible" not in text:
        errors.append("identity_prompt_builder must apply Style Bible v1")
    if text.count("def build_identity_prompt") != 1:
        errors.append("only one build_identity_prompt entry allowed")
    return errors


def run_all_checks() -> tuple[bool, list[str]]:
    errors: list[str] = []
    checks = (
        check_single_get_visual_entry,
        check_no_visual_context_imports,
        check_forbidden_visual_modules,
        check_provider_no_registry_writes,
        check_visual_api_read_only,
        check_pipeline_integrity,
        check_identity_prompt_builder_only,
        check_registry_schema_stable,
        check_style_bible_single_engine_entry,
    )
    for fn in checks:
        errors.extend(fn())
    return (not errors, errors)

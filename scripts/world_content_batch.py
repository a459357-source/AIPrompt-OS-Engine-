#!/usr/bin/env python3
"""CLI — V6 World Content Generation Template Pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.templates.world_content_pack import (
    apply_dataset_import,
    build_entity_prompt,
    build_full_dataset_prompt,
    default_batch_plan,
    validate_world_dataset,
)


def _plan_from_args(args: argparse.Namespace) -> dict:
    plan = default_batch_plan()
    for key in plan:
        val = getattr(args, key, None)
        if val is not None:
            plan[key] = int(val)
    return plan


def cmd_prompt(args: argparse.Namespace) -> int:
    if args.full:
        print(build_full_dataset_prompt(_plan_from_args(args)))
        return 0
    if not args.type:
        print("error: --type required unless --full", file=sys.stderr)
        return 1
    context = {}
    if args.context_file:
        context = json.loads(Path(args.context_file).read_text(encoding="utf-8"))
    print(build_entity_prompt(args.type, args.count, context=context))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    report = validate_world_dataset(data)
    out = {k: v for k, v in report.items() if k != "dataset"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


def cmd_import(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    result = apply_dataset_import(
        data,
        persist=not args.dry_run,
        merge_world_pack=not args.templates_only,
        merge_templates=not args.world_only,
    )
    out = {k: v for k, v in result.items() if k != "dataset"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if result.get("imported") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="V6 World Content Generation Template Pack")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prompt = sub.add_parser("prompt", help="Print AI-ready generation prompt")
    p_prompt.add_argument("--type", choices=["character", "location", "event", "faction"])
    p_prompt.add_argument("--count", type=int, default=5)
    p_prompt.add_argument("--full", action="store_true", help="Full dataset one-shot prompt")
    p_prompt.add_argument("--characters", type=int, help="Override full batch plan")
    p_prompt.add_argument("--locations", type=int)
    p_prompt.add_argument("--events", type=int)
    p_prompt.add_argument("--factions", type=int)
    p_prompt.add_argument("--context-file", help="JSON with existing characters/locations/factions")
    p_prompt.set_defaults(func=cmd_prompt)

    p_val = sub.add_parser("validate", help="Validate generated dataset JSON")
    p_val.add_argument("file")
    p_val.set_defaults(func=cmd_validate)

    p_imp = sub.add_parser("import", help="Import validated dataset into world_pack + templates")
    p_imp.add_argument("file")
    p_imp.add_argument("--dry-run", action="store_true")
    p_imp.add_argument("--world-only", action="store_true")
    p_imp.add_argument("--templates-only", action="store_true")
    p_imp.set_defaults(func=cmd_import)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

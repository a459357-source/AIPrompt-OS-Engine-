#!/usr/bin/env python3
"""V6 One-click World Bootstrap CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.templates.world_bootstrap import (
    apply_bootstrap_import,
    build_bootstrap_prompt,
    generate_bootstrap_dataset,
    normalize_bootstrap_input,
    validate_bootstrap_dataset,
)


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_prompt(args: argparse.Namespace) -> int:
    cfg = normalize_bootstrap_input(_load_config(args.config))
    print(build_bootstrap_prompt(cfg))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    report = validate_bootstrap_dataset(data)
    print(json.dumps({k: v for k, v in report.items() if k != "dataset"}, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


def cmd_import(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    result = apply_bootstrap_import(data, persist=not args.dry_run)
    print(json.dumps({k: v for k, v in result.items() if k != "dataset"}, ensure_ascii=False, indent=2))
    return 0 if result.get("imported") else 1


def cmd_run(args: argparse.Namespace) -> int:
    cfg = normalize_bootstrap_input(_load_config(args.config))
    gen = generate_bootstrap_dataset(cfg, use_llm=not args.prompt_only)

    if args.prompt_only or not gen.get("generated"):
        if gen.get("prompt"):
            print(gen["prompt"])
        if gen.get("error"):
            print(json.dumps({"error": gen["error"]}, ensure_ascii=False), file=sys.stderr)
        if args.output and gen.get("prompt"):
            Path(args.output).write_text(gen["prompt"], encoding="utf-8")
        return 2 if not gen.get("generated") else 0

    dataset = gen["dataset"]
    if args.output:
        Path(args.output).write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.no_import:
        print(json.dumps({"generated": True, "validation": gen.get("validation")}, ensure_ascii=False, indent=2))
        return 0

    result = apply_bootstrap_import(dataset, persist=not args.dry_run)
    print(json.dumps({k: v for k, v in result.items() if k != "dataset"}, ensure_ascii=False, indent=2))
    return 0 if result.get("imported") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="V6 One-click World Bootstrap")
    sub = parser.add_subparsers(dest="command", required=True)

    p_prompt = sub.add_parser("prompt", help="Print bootstrap prompt")
    p_prompt.add_argument("--config", help="bootstrap_input JSON file")
    p_prompt.set_defaults(func=cmd_prompt)

    p_val = sub.add_parser("validate", help="Validate bootstrap dataset JSON")
    p_val.add_argument("file")
    p_val.set_defaults(func=cmd_validate)

    p_imp = sub.add_parser("import", help="Import bootstrap dataset")
    p_imp.add_argument("file")
    p_imp.add_argument("--dry-run", action="store_true")
    p_imp.set_defaults(func=cmd_import)

    p_run = sub.add_parser("run", help="Generate + validate + import (one-click)")
    p_run.add_argument("--config", help="bootstrap_input JSON file")
    p_run.add_argument("--prompt-only", action="store_true", help="Only output prompt (no LLM)")
    p_run.add_argument("--no-import", action="store_true", help="Generate only, skip import")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--output", help="Write dataset or prompt to file")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""V6 Freeze Checklist — CI / pre-commit architecture lock runner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.visual.freeze_check import run_all_checks


def main() -> int:
    ok, errors = run_all_checks()
    if ok:
        print("V6 Freeze Check: PASS")
        return 0
    print("V6 Freeze Check: FAIL")
    for err in errors:
        print(f"  - {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

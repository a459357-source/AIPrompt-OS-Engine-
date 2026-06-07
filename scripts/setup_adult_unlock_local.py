#!/usr/bin/env python3
"""One-time bootstrap: create signing secret + local key generator (tools/local/, gitignored)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.adult_unlock import generate_unlock_key, secret_path, write_secret

LOCAL_DIR = ROOT / "tools" / "local"
GENERATOR_PATH = LOCAL_DIR / "generate_adult_key.py"

GENERATOR_SOURCE = '''#!/usr/bin/env python3
"""Local adult-mode unlock key generator (NOT in git). Uses data/adult_unlock_secret."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.adult_unlock import generate_unlock_key, secret_path, write_secret


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PromptOS adult-mode unlock keys")
    parser.add_argument("-n", "--count", type=int, default=1, help="Number of keys to generate")
    parser.add_argument("--init", action="store_true", help="Create data/adult_unlock_secret if missing")
    args = parser.parse_args()

    if args.init or not secret_path().is_file():
        write_secret()
        print(f"已创建签名密钥: {secret_path()}")

    if not secret_path().is_file():
        print("缺少签名密钥，请先运行: python tools/local/generate_adult_key.py --init", file=sys.stderr)
        return 1

    count = max(1, args.count)
    for i in range(count):
        print(generate_unlock_key())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    if not secret_path().is_file():
        write_secret()
        print(f"已创建签名密钥: {secret_path()}")
    else:
        print(f"签名密钥已存在: {secret_path()}")

    GENERATOR_PATH.write_text(GENERATOR_SOURCE, encoding="utf-8")
    print(f"已写入本地生成器: {GENERATOR_PATH}")
    print()
    print("用法:")
    print("  python tools/local/generate_adult_key.py")
    print("  python tools/local/generate_adult_key.py -n 5")
    print()
    print("示例密钥:")
    print(generate_unlock_key())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

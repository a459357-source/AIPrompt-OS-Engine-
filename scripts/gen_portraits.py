"""
批量生成所有角色立绘
从 prompt-os-engine/ 运行: python scripts/gen_portraits.py
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine import io_utils
from engine.visual.asset_manager import get_or_request_character_portrait
from engine.visual.visual_api import public_image_url

def main():
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    characters = world_pack.get("world", world_pack).get("characters", [])

    print(f"共 {len(characters)} 个角色，逐一生成立绘...\n")

    results = []
    for ch in characters:
        name = ch["name"]
        print(f"[{name}] 生成中...", end=" ", flush=True)
        try:
            record = get_or_request_character_portrait(
                name=name,
                world_pack=world_pack,
                turn=1,
                force=True,
            )
            image_path = record.get("image_path", "")
            url = public_image_url(image_path) if image_path else ""
            print(f"[OK] {url}")
            results.append({"name": name, "url": url, "path": image_path})
        except Exception as e:
            print(f"[FAIL] {e}")
            results.append({"name": name, "error": str(e)})

    print("\n===== Results =====")
    for r in results:
        print(f"  {r['name']}: {r.get('url') or r.get('error', '无')}")

    return 0 if all("url" in r for r in results) else 1

if __name__ == "__main__":
    sys.exit(main())

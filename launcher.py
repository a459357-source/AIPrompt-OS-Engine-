#!/usr/bin/env python3
"""PromptOS desktop launcher — starts API + bundled React UI on :8000."""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    os.chdir(ROOT)
    sys.path.insert(0, str(Path(sys._MEIPASS)))
else:
    ROOT = Path(__file__).resolve().parent
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

import config
config.ensure_runtime_files()


def _open_browser() -> None:
    time.sleep(2.5)
    url = config.frontend_url("/")
    webbrowser.open(url)


def main() -> None:
    print("PromptOS — 启动中…")
    print(f"  数据目录: {config.DATA_DIR}")
    print(f"  访问地址: {config.frontend_url('/')}")
    print("  关闭本窗口即停止服务\n")

    threading.Thread(target=_open_browser, daemon=True).start()

    import uvicorn
    uvicorn.run(
        "ui.web_app:app",
        host="127.0.0.1",
        port=int(os.environ.get("PROMPTOS_PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    main()

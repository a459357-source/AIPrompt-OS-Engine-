#!/usr/bin/env python3
"""PromptOS desktop launcher — starts API + bundled React UI on :8000."""
from __future__ import annotations

import logging
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
config.setup_logging(console=True)
logger = logging.getLogger("launcher")


def _open_browser(port: int) -> None:
    """Open UI after the local server is accepting connections."""
    url = config.frontend_url("/")

    def _open() -> None:
        import socket
        for _ in range(30):
            time.sleep(0.5)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(("127.0.0.1", port))
                s.close()
                break
            except (ConnectionRefusedError, OSError):
                continue
        logger.info("Opening browser → %s", url)
        try:
            webbrowser.open(url)
        except Exception as exc:
            logger.warning("Failed to open browser: %s", exc)
            print(f"  请手动打开: {url}")

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    print("PromptOS — 启动中…")
    print(f"  数据目录: {config.DATA_DIR}")
    print(f"  访问地址: {config.frontend_url('/')}")
    print(f"  运行日志: {config.LOG_PATH}")
    print(f"  错误日志: {config.ERROR_LOG_PATH}")
    print("  关闭本窗口即停止服务\n")

    logger.info("PromptOS starting — UI %s", config.frontend_url("/"))

    port = int(os.environ.get("PROMPTOS_PORT", "8000"))
    _open_browser(port)

    import uvicorn
    uvicorn.run(
        "ui.web_app:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

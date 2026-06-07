#!/usr/bin/env python3
"""Exit with error if a TCP port is already in use on 127.0.0.1."""
from __future__ import annotations

import socket
import sys


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: port_guard.py <port>")
        return 2
    port = int(sys.argv[1])
    if port_in_use(port):
        print(f"[ERROR] Port {port} is in use. Run stop.bat first.")
        print("  Or end python/node in Task Manager.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

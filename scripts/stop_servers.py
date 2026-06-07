#!/usr/bin/env python3
"""Stop processes listening on PromptOS dev ports (8000, 5173)."""
from __future__ import annotations

import subprocess
import sys


def _pids_on_port(port: int) -> list[int]:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    pids: set[int] = set()
    needle = f":{port}"
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        if needle not in line.split()[1]:
            continue
        parts = line.split()
        if parts:
            try:
                pids.add(int(parts[-1]))
            except ValueError:
                pass
    return sorted(pids)


def main() -> int:
    ports = [8000, 5173]
    if len(sys.argv) > 1:
        ports = [int(p) for p in sys.argv[1:]]

    killed = 0
    for port in ports:
        for pid in _pids_on_port(port):
            if pid <= 0:
                continue
            print(f"Stopping PID {pid} (port {port})...")
            r = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                text=True,
            )
            if r.returncode == 0:
                killed += 1
            else:
                print(r.stderr.strip() or r.stdout.strip())

    if killed:
        print(f"Done. Stopped {killed} process(es).")
    else:
        print("No listening process on ports:", ", ".join(map(str, ports)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

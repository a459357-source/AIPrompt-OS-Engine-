"""
cursor_sync.py — External AI orchestration sync client for /game runtime reporting.

Design contract:
  - Reports system state only — NEVER controls story, options, or game flow.
  - Fire-and-forget: failures are silently swallowed.
  - Must NOT import game engine modules (avoid side effects).
"""

from datetime import datetime, timezone
from typing import Any

import requests

SYNC_ENDPOINT = "http://localhost:8000/api/cursor-report"


def send_cursor_report(report: dict[str, Any]) -> None:
    """Send a structured runtime report to the external orchestration endpoint.

    If the endpoint is unreachable or returns an error, the failure is
    silently ignored — this system is read-only reporting only.
    """
    payload = dict(report)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    try:
        requests.post(SYNC_ENDPOINT, json=payload, timeout=2)
    except Exception:
        pass

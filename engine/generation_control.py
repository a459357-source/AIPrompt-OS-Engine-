"""In-flight generation control: cancel flag and partial story persistence."""

from __future__ import annotations

import threading

_cancel_event = threading.Event()
_lock = threading.Lock()
_partial_story: str = ""


def clear_cancel() -> None:
    _cancel_event.clear()


def request_cancel() -> None:
    _cancel_event.set()


def is_cancelled() -> bool:
    return _cancel_event.is_set()


def update_partial_story(text: str) -> None:
    global _partial_story
    with _lock:
        _partial_story = text


def get_partial_story() -> str:
    with _lock:
        return _partial_story


def reset_partial() -> None:
    global _partial_story
    with _lock:
        _partial_story = ""

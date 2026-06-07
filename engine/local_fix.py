"""Local repair of AI JSON responses — no extra API calls."""

from __future__ import annotations

import json
import logging
from typing import Any

import config

logger = logging.getLogger(__name__)

_TRUST_KEYS = ("trust", "affection", "respect", "dependence", "hostility", "attraction")


def salvage_json(raw: str) -> dict | None:
    """Try to recover a dict from truncated or malformed JSON."""
    if not raw or not raw.strip():
        return None

    text = raw.strip()
    fenced = _extract_fenced_json(text)
    if fenced:
        text = fenced

    for candidate in (text, _close_json_brackets(text)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    story = _salvage_story_string(text)
    if story:
        return {
            "story": story,
            "state": {},
            "options": [],
        }
    return None


def fix_response(data: dict, *, relationship_stages: list[str] | None = None) -> dict:
    """Apply local fixes to a parsed AI response."""
    if not isinstance(data, dict):
        return data

    fixed = dict(data)
    story = fixed.get("story")
    if isinstance(story, str):
        fixed["story"] = story.strip()
    elif story is None:
        fixed["story"] = ""

    state = fixed.get("state")
    if not isinstance(state, dict):
        state = {}
    fixed["state"] = _fix_state(state, relationship_stages=relationship_stages)

    opts = fixed.get("options")
    if not isinstance(opts, list):
        opts = []
    fixed["options"] = _fix_options(opts)

    return fixed


def _extract_fenced_json(text: str) -> str | None:
    if "```json" in text:
        start = text.index("```json") + len("```json")
        end = text.rfind("```")
        if end > start:
            return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.rfind("```")
        if end > start:
            return text[start:end].strip()
    return None


def _close_json_brackets(text: str) -> str:
    """Best-effort close open strings/objects/arrays."""
    out = text.rstrip()
    if out.endswith(","):
        out = out[:-1]

    in_string = False
    escape = False
    stack: list[str] = []
    for ch in out:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in ("}", "]") and stack and stack[-1] == ch:
            stack.pop()

    if in_string:
        out += '"'
    out += "".join(reversed(stack))
    return out


def _salvage_story_string(text: str) -> str | None:
    marker = '"story"'
    idx = text.find(marker)
    if idx < 0:
        return None
    i = idx + len(marker)
    while i < len(text) and text[i] in " \t\r\n:":
        i += 1
    if i >= len(text) or text[i] != '"':
        return None
    i += 1

    chars: list[str] = []
    escape = False
    while i < len(text):
        ch = text[i]
        if escape:
            if ch == "n":
                chars.append("\n")
            elif ch == "t":
                chars.append("\t")
            elif ch in ('"', "\\", "/"):
                chars.append(ch)
            else:
                chars.append(ch)
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == '"':
            break
        else:
            chars.append(ch)
        i += 1

    story = "".join(chars).strip()
    return story if len(story) >= 20 else None


def _fix_state(state: dict, *, relationship_stages: list[str] | None = None) -> dict:
    fixed = dict(state)
    status = fixed.get("status", "")
    if status not in config.STATUS_ORDER:
        fixed["status"] = config.STATUS_ORDER[0]

    chars = fixed.get("characters")
    if not isinstance(chars, dict):
        chars = {}
    fixed_chars: dict[str, Any] = {}
    for key, ch in chars.items():
        if not isinstance(ch, dict):
            continue
        entry = dict(ch)
        for metric in _TRUST_KEYS:
            if metric in entry:
                entry[metric] = _clamp_int(entry[metric], 0, 100)
        rel = entry.get("relationship") or entry.get("relation")
        if isinstance(rel, str) and relationship_stages:
            entry["relationship"] = _clamp_stage(rel, relationship_stages)
        fixed_chars[key] = entry
    fixed["characters"] = fixed_chars
    return fixed


def _fix_options(opts: list) -> list[str]:
    expected = config.OPTION_COUNT
    cleaned: list[str] = []
    for opt in opts:
        if isinstance(opt, str) and opt.strip():
            cleaned.append(opt.strip()[:500])
        elif opt is not None:
            cleaned.append(str(opt).strip()[:500])

    while len(cleaned) < expected:
        idx = len(cleaned) + 1
        if cleaned:
            cleaned.append(f"继续观察局势（选项 {idx}）")
        else:
            cleaned.append(f"继续推进剧情（选项 {idx}）")
    return cleaned[:expected]


def _clamp_int(value: Any, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def _clamp_stage(stage: str, stages: list[str]) -> str:
    if stage in stages:
        return stage
    for s in stages:
        if stage in s or s in stage:
            return s
    return stages[0] if stages else stage


def log_fixes(before: dict, after: dict) -> None:
    """Log summary of local fixes applied."""
    if before.get("story", "") != after.get("story", ""):
        logger.info("local_fix: story trimmed/normalized")
    if len(before.get("options") or []) != len(after.get("options") or []):
        logger.info(
            "local_fix: options padded %d → %d",
            len(before.get("options") or []),
            len(after.get("options") or []),
        )

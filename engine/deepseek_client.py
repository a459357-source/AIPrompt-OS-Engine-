"""
deepseek_client.py — DeepSeek Chat Completions API client
==========================================================
Minimal wrapper: sends system + user messages, returns the
assistant's JSON response parsed into a dict.

Endpoint : https://api.deepseek.com/chat/completions
Model    : deepseek-chat
"""

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import requests

import config

logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """Raised when the API returns a non-200 or the response is unparseable."""


StoryDeltaCallback = Callable[[str], None]
StoryResetCallback = Callable[[], None]


def parse_story_from_partial_json(raw: str) -> tuple[str, bool]:
    """
    Extract the JSON string value of the ``story`` field from partial model output.

    Returns (decoded_story_text, is_complete).
    """
    marker = '"story"'
    idx = raw.find(marker)
    if idx < 0:
        return "", False

    i = idx + len(marker)
    while i < len(raw) and raw[i] in " \t\r\n":
        i += 1
    if i >= len(raw) or raw[i] != ":":
        return "", False
    i += 1
    while i < len(raw) and raw[i] in " \t\r\n":
        i += 1
    if i >= len(raw) or raw[i] != '"':
        return "", False
    i += 1

    chars: list[str] = []
    escape = False
    while i < len(raw):
        ch = raw[i]
        if escape:
            if ch == "n":
                chars.append("\n")
            elif ch == "t":
                chars.append("\t")
            elif ch == "r":
                chars.append("\r")
            elif ch in ('"', "\\", "/"):
                chars.append(ch)
            elif ch == "u" and i + 4 < len(raw):
                try:
                    chars.append(chr(int(raw[i + 1 : i + 5], 16)))
                    i += 4
                except ValueError:
                    chars.append(ch)
            else:
                chars.append(ch)
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == '"':
            return "".join(chars), True
        else:
            chars.append(ch)
        i += 1
    return "".join(chars), False


def _emit_story_deltas(
    raw: str,
    *,
    emitted_len: int,
    on_story_delta: StoryDeltaCallback | None,
) -> int:
    if not on_story_delta:
        return emitted_len
    story, _ = parse_story_from_partial_json(raw)
    if len(story) > emitted_len:
        on_story_delta(story[emitted_len:])
        return len(story)
    return emitted_len


def call_deepseek(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    skip_validation: bool = False,
    stream: bool | None = None,
    on_story_delta: StoryDeltaCallback | None = None,
    on_story_reset: StoryResetCallback | None = None,
) -> dict:
    """
    Call the DeepSeek Chat Completions API and return the parsed JSON body.
    Auto-retries with 2x max_tokens on JSON truncation (up to 2 retries).

    When *stream* is True (or config.STREAM with delta callbacks), streams the
    ``story`` field to *on_story_delta* while accumulating the full JSON.
    """
    if not config.DEEPSEEK_API_KEY:
        raise DeepSeekError("未配置 DeepSeek API Key，请在设置页或首次启动弹窗中填写")

    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    temp = temperature if temperature is not None else config.TEMPERATURE
    mt = max_tokens if max_tokens is not None else config.MAX_TOKENS
    use_stream = stream if stream is not None else bool(
        config.STREAM and on_story_delta is not None
    )

    for attempt in range(config.API_MAX_PARSE_ATTEMPTS):
        if attempt > 0 and on_story_reset:
            on_story_reset()

        if use_stream:
            raw_content, body = _request_stream(
                headers,
                system_prompt,
                user_prompt,
                temp=temp,
                mt=mt,
                on_story_delta=on_story_delta,
            )
        else:
            raw_content, body = _request_sync(
                headers,
                system_prompt,
                user_prompt,
                temp=temp,
                mt=mt,
            )

        result, parse_error = _parse_json_content(raw_content)
        if result is None:
            from engine.local_fix import salvage_json

            salvaged = salvage_json(raw_content)
            if salvaged is not None:
                result = salvaged
                logger.warning("JSON parse failed — recovered via local_fix salvage")

        if result is not None:
            from engine.local_fix import fix_response

            result = fix_response(result)
            if not skip_validation:
                _validate_response(result)
            _log_usage(body, result)
            return result

        if attempt < config.API_MAX_PARSE_ATTEMPTS - 1:
            logger.warning(
                "JSON parse failed (attempt %d/%d) — retrying API once",
                attempt + 1,
                config.API_MAX_PARSE_ATTEMPTS,
            )
            continue

        raise DeepSeekError(
            f"AI 返回无法解析，请到设置页面将「AI 最大 Token」调高（当前 {mt}）"
        ) from parse_error

    raise DeepSeekError("AI 生成失败，请重试")


def _build_payload(
    system_prompt: str,
    user_prompt: str,
    *,
    temp: float,
    mt: int,
    stream: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temp,
        "max_tokens": mt,
        "top_p": config.TOP_P,
        "stream": stream,
        "response_format": {"type": "json_object"},
    }
    return payload


def _request_sync(
    headers: dict[str, str],
    system_prompt: str,
    user_prompt: str,
    *,
    temp: float,
    mt: int,
) -> tuple[str, dict]:
    payload = _build_payload(system_prompt, user_prompt, temp=temp, mt=mt, stream=False)
    logger.info(
        "Calling DeepSeek API → %s (sync, max_tokens=%d)",
        config.DEEPSEEK_ENDPOINT,
        mt,
    )
    resp = _post_with_retries(headers, payload)
    body = resp.json()
    try:
        raw_content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise DeepSeekError(f"Unexpected API response shape: {body}") from exc
    return raw_content, body


def _request_stream(
    headers: dict[str, str],
    system_prompt: str,
    user_prompt: str,
    *,
    temp: float,
    mt: int,
    on_story_delta: StoryDeltaCallback | None,
) -> tuple[str, dict]:
    payload = _build_payload(system_prompt, user_prompt, temp=temp, mt=mt, stream=True)
    logger.info(
        "Calling DeepSeek API → %s (stream, max_tokens=%d)",
        config.DEEPSEEK_ENDPOINT,
        mt,
    )
    resp = _post_with_retries(headers, payload, stream=True)

    accumulated = ""
    emitted_len = 0
    body: dict[str, Any] = {"model": config.DEEPSEEK_MODEL, "usage": {}}

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:].strip()
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        if "usage" in chunk and chunk["usage"]:
            body["usage"] = chunk["usage"]
        if chunk.get("model"):
            body["model"] = chunk["model"]
        if chunk.get("id"):
            body["id"] = chunk["id"]

        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content") or ""
        if not piece:
            continue
        accumulated += piece
        emitted_len = _emit_story_deltas(
            accumulated,
            emitted_len=emitted_len,
            on_story_delta=on_story_delta,
        )

    return accumulated, body


def _post_with_retries(
    headers: dict[str, str],
    payload: dict[str, Any],
    *,
    stream: bool = False,
) -> requests.Response:
    max_http_retries = 2
    for http_attempt in range(max_http_retries):
        try:
            resp = requests.post(
                config.DEEPSEEK_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=90,
                stream=stream,
            )
        except requests.RequestException as exc:
            if http_attempt < max_http_retries - 1:
                delay = 2 ** http_attempt
                logger.warning(
                    "HTTP request failed (attempt %d/%d): %s — retrying in %ds",
                    http_attempt + 1,
                    max_http_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
                continue
            raise DeepSeekError(
                f"HTTP request failed after {max_http_retries} attempts: {exc}"
            ) from exc

        if resp.status_code == 200:
            return resp

        retryable = resp.status_code in (429, 500, 502, 503, 504)
        if retryable and http_attempt < max_http_retries - 1:
            delay = 2 ** http_attempt
            logger.warning(
                "API returned %d (attempt %d/%d) — retrying in %ds",
                resp.status_code,
                http_attempt + 1,
                max_http_retries,
                delay,
            )
            time.sleep(delay)
            continue

        raise DeepSeekError(f"API returned {resp.status_code}: {resp.text[:500]}")

    raise DeepSeekError("HTTP request failed")


def _parse_json_content(raw_content: str) -> tuple[dict | None, Exception | None]:
    try:
        return json.loads(raw_content), None
    except json.JSONDecodeError as exc:
        parse_error = exc
        stripped = _extract_json_from_markdown(raw_content)
        if stripped:
            try:
                return json.loads(stripped), None
            except json.JSONDecodeError:
                pass
        return None, parse_error


def _extract_json_from_markdown(text: str) -> str | None:
    """If the model wrapped JSON in ``` fences, extract the content."""
    if "```json" in text:
        start = text.index("```json") + len("```json")
        end = text.rindex("```")
        if end > start:
            return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.rindex("```")
        if end > start:
            return text[start:end].strip()
    return None


def _log_usage(body: dict, result: dict) -> None:
    """Append API usage stats to api_usage.jsonl (non-blocking, best-effort)."""
    try:
        from datetime import datetime
        from pathlib import Path

        usage = body.get("usage", {})
        entry = {
            "timestamp": datetime.now().isoformat(),
            "model": body.get("model", "?"),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "story_chars": len(result.get("story", "")),
            "api_id": body.get("id", ""),
        }
        path = Path(config.API_USAGE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _validate_response(data: dict) -> None:
    """
    Log validation warnings only — local_fix handles repair; no API retry.
    """
    from engine.state_manager import validate_response

    warnings = validate_response(data)
    for w in warnings:
        logger.warning("AI response validation: %s", w)

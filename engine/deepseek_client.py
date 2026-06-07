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
import requests

import config

logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """Raised when the API returns a non-200 or the response is unparseable."""


def call_deepseek(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    skip_validation: bool = False,
) -> dict:
    """
    Call the DeepSeek Chat Completions API and return the parsed JSON body.
    Auto-retries with 2x max_tokens on JSON truncation (up to 2 retries).
    """
    if not config.DEEPSEEK_API_KEY:
        raise DeepSeekError("未配置 DeepSeek API Key，请在设置页或首次启动弹窗中填写")

    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    temp = temperature if temperature is not None else config.TEMPERATURE
    mt = max_tokens if max_tokens is not None else config.MAX_TOKENS

    for attempt in range(3):
        payload = {
            "model": config.DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temp,
            "max_tokens": mt,
            "top_p": config.TOP_P,
            "stream": False,
            "response_format": {"type": "json_object"},
        }

        logger.info("Calling DeepSeek API → %s (attempt %d, max_tokens=%d)",
                     config.DEEPSEEK_ENDPOINT, attempt + 1, mt)

        # ── HTTP request with retry on transient errors ──────────
        MAX_HTTP_RETRIES = 3
        for http_attempt in range(MAX_HTTP_RETRIES):
            try:
                resp = requests.post(
                    config.DEEPSEEK_ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=90,
                )
            except requests.RequestException as exc:
                if http_attempt < MAX_HTTP_RETRIES - 1:
                    delay = 2 ** http_attempt
                    logger.warning(
                        "HTTP request failed (attempt %d/%d): %s — retrying in %ds",
                        http_attempt + 1, MAX_HTTP_RETRIES, exc, delay,
                    )
                    time.sleep(delay)
                    continue
                raise DeepSeekError(f"HTTP request failed after {MAX_HTTP_RETRIES} attempts: {exc}") from exc

            # Success
            if resp.status_code == 200:
                break

            # Retryable error codes
            retryable = resp.status_code in (429, 500, 502, 503, 504)
            if retryable and http_attempt < MAX_HTTP_RETRIES - 1:
                delay = 2 ** http_attempt
                logger.warning(
                    "API returned %d (attempt %d/%d) — retrying in %ds",
                    resp.status_code, http_attempt + 1, MAX_HTTP_RETRIES, delay,
                )
                time.sleep(delay)
                continue

            # Non-retryable or exhausted retries
            raise DeepSeekError(
                f"API returned {resp.status_code}: {resp.text[:500]}"
            )

        body = resp.json()

        try:
            raw_content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise DeepSeekError(f"Unexpected API response shape: {body}") from exc

        # Try parsing JSON
        result = None
        parse_error = None
        try:
            result = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            parse_error = exc
            stripped = _extract_json_from_markdown(raw_content)
            if stripped:
                try:
                    result = json.loads(stripped)
                    parse_error = None
                except json.JSONDecodeError:
                    pass

        if result is not None:
            if not skip_validation:
                _validate_response(result)
            _log_usage(body, result)
            return result

        # JSON parse failed — likely truncated, retry with more tokens
        if attempt < 2:
            new_mt = min(mt * 2, 16384)
            if new_mt > mt:
                logger.warning(
                    "JSON parse failed (attempt %d), retrying with max_tokens=%d (was %d). "
                    "Tip: increase 'AI 最大 Token' in settings.",
                    attempt + 1, new_mt, mt
                )
                mt = new_mt
                continue

        # Final attempt failed
        raise DeepSeekError(
            f"AI 返回被截断，请到设置页面将「AI 最大 Token」调高（当前 {mt}）"
        ) from parse_error

    raise DeepSeekError("AI 生成失败，请重试")


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
        pass  # never let usage logging crash the game


def _validate_response(data: dict) -> None:
    """
    Validate the AI response structure.  Delegates to state_manager's
    validate_response (which performs the same checks plus additional
    state-machine validation) and raises DeepSeekError on any failure.
    """
    from engine.state_manager import validate_response
    warnings = validate_response(data)
    if warnings:
        raise DeepSeekError(
            f"AI response validation failed: {'; '.join(warnings)}"
        )

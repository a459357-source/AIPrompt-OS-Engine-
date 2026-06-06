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
import requests

import config

logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """Raised when the API returns a non-200 or the response is unparseable."""


def call_deepseek(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.8,
    max_tokens: int = 2048,
) -> dict:
    """
    Call the DeepSeek Chat Completions API and return the parsed JSON body.

    The API is expected to return a JSON object in the format:
        {"story": "...", "state": {...}, "options": [...]}

    Raises DeepSeekError on HTTP failure or JSON parse failure.
    """

    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},  # force JSON output
    }

    logger.info("Calling DeepSeek API → %s", config.DEEPSEEK_ENDPOINT)
    logger.debug("Payload: %s", json.dumps(payload, ensure_ascii=False, indent=2))

    try:
        resp = requests.post(
            config.DEEPSEEK_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise DeepSeekError(f"HTTP request failed: {exc}") from exc

    if resp.status_code != 200:
        raise DeepSeekError(
            f"API returned {resp.status_code}: {resp.text[:500]}"
        )

    body = resp.json()
    logger.debug("Raw API response: %s", json.dumps(body, ensure_ascii=False, indent=2))

    # Extract the assistant message content
    try:
        raw_content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise DeepSeekError(f"Unexpected API response shape: {body}") from exc

    # Parse the JSON inside the content string
    try:
        result = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        # If the model returned markdown-fenced JSON, try to extract it
        stripped = _extract_json_from_markdown(raw_content)
        if stripped:
            try:
                result = json.loads(stripped)
            except json.JSONDecodeError:
                raise DeepSeekError(
                    f"Model returned unparseable JSON: {raw_content[:500]}"
                ) from exc
        else:
            raise DeepSeekError(
                f"Model returned unparseable JSON: {raw_content[:500]}"
            ) from exc

    # Validate required keys
    _validate_response(result)

    # Log API usage for analytics
    _log_usage(body, result)

    return result


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
        import config as cfg
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
        path = Path(cfg.API_USAGE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        import json
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let usage logging crash the game


def _validate_response(data: dict) -> None:
    """Ensure the response contains the required top-level keys."""
    required = ["story", "state", "options"]
    missing = [k for k in required if k not in data]
    if missing:
        raise DeepSeekError(
            f"Response missing required keys: {missing}. Got keys: {list(data.keys())}"
        )
    if not isinstance(data["options"], list) or len(data["options"]) != 4:
        logger.warning(
            "options should be a list of exactly 4 strings; got: %s", data.get("options")
        )

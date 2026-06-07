"""Adult mode unlock keys (HMAC). Signing secret lives in data/adult_unlock_secret (gitignored)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from pathlib import Path

_KEY_RE = re.compile(r"^POS-A-([A-Z2-7]{8})-([A-Z2-7]{16})$")


def secret_path() -> Path:
    import config

    return config.DATA_DIR / "adult_unlock_secret"


def load_secret() -> bytes:
    path = secret_path()
    if not path.is_file():
        return b""
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return b""
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return raw.encode("utf-8")


def write_secret(raw: bytes | None = None) -> bytes:
    """Create or overwrite the local signing secret (for setup / key generator)."""
    secret = raw if raw is not None else secrets.token_bytes(32)
    path = secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(secret.hex(), encoding="utf-8")
    return secret


def normalize_unlock_key(key: str) -> str:
    return re.sub(r"\s+", "", str(key or "").strip().upper())


def _format_key(key_id: str, sig: str) -> str:
    return f"POS-A-{key_id}-{sig}"


def sign_key_id(key_id: str, secret: bytes) -> str:
    digest = hmac.new(secret, key_id.encode("ascii"), hashlib.sha256).digest()[:10]
    return base64.b32encode(digest).decode("ascii").rstrip("=")[:16]


def verify_unlock_key(key: str, *, secret: bytes | None = None) -> bool:
    normalized = normalize_unlock_key(key)
    m = _KEY_RE.match(normalized)
    if not m:
        return False
    key_id, sig = m.group(1), m.group(2)
    sec = secret if secret is not None else load_secret()
    if not sec:
        return False
    expected = sign_key_id(key_id, sec)
    return hmac.compare_digest(sig, expected)


def generate_unlock_key(*, secret: bytes | None = None) -> str:
    """Generate a new unlock key (requires signing secret on disk)."""
    sec = secret if secret is not None else load_secret()
    if not sec:
        raise RuntimeError(
            "缺少 data/adult_unlock_secret。请先运行: python scripts/setup_adult_unlock_local.py"
        )
    key_id = base64.b32encode(secrets.token_bytes(5)).decode("ascii").rstrip("=")[:8]
    sig = sign_key_id(key_id, sec)
    return _format_key(key_id, sig)


def mask_unlock_key(key: str) -> str:
    normalized = normalize_unlock_key(key)
    m = _KEY_RE.match(normalized)
    if not m:
        return "***"
    key_id = m.group(1)
    return f"POS-A-{key_id[:3]}…{key_id[-2:]}-****"

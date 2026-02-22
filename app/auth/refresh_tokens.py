from __future__ import annotations

import hashlib
import secrets


def generate_refresh_token() -> str:
    # URL-safe, đủ dài cho refresh
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw: str) -> str:
    # lưu hash vào DB, không lưu raw
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
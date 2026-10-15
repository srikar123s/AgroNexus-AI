"""Small dependency-free authentication primitives for local and hosted use."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, Header, HTTPException

from config import AUTH_MODE, JWT_SECRET
from database.database import connect

ALGORITHM = "HS256"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, digest = encoded.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(rounds))
        return hmac.compare_digest(candidate, _unb64(digest))
    except (ValueError, TypeError):
        return False


def create_token(subject: str, role: str, ttl_seconds: int, token_type: str = "access") -> str:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET must be configured when AUTH_MODE=required")
    header = _b64(json.dumps({"alg": ALGORITHM, "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": subject, "role": role, "type": token_type, "exp": int(time.time()) + ttl_seconds}, separators=(",", ":")).encode())
    signing = f"{header}.{payload}".encode()
    return f"{header}.{payload}.{_b64(hmac.new(JWT_SECRET.encode(), signing, hashlib.sha256).digest())}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        expected = _b64(hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        data = json.loads(_unb64(payload))
        if data.get("exp", 0) < time.time():
            raise ValueError
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token")


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any] | None:
    if AUTH_MODE != "required" and not authorization:
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer authentication required")
    claims = decode_token(authorization.split(" ", 1)[1])
    with connect() as db:
        row = db.execute(
            "SELECT user_id, email, username, phone, role, is_active FROM users WHERE user_id = ?",
            (claims["sub"],),
        ).fetchone()
    if not row or not row["is_active"]:
        raise HTTPException(status_code=401, detail="User is inactive or unknown")
    return dict(row)


def require_roles(*roles: str):
    def dependency(user: dict[str, Any] | None = Depends(current_user)):
        if user is None or user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return dependency

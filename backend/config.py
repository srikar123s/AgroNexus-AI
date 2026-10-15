"""Environment-backed runtime configuration.

SQLite remains the default so a checkout can run without infrastructure. Set
DATABASE_URL to a PostgreSQL URL in hosted environments; the URL is exposed
for migration tooling and future repository adapters.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent


def setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


DATABASE_URL = setting("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'database' / 'agronexus.db'}")
AUTH_MODE = setting("AUTH_MODE", "demo").lower()  # demo or required
# A process-local secret keeps demo auth usable without ever shipping a secret.
# Hosted/required mode must provide JWT_SECRET explicitly.
JWT_SECRET = setting("JWT_SECRET") or secrets.token_urlsafe(48)
JWT_TTL_MINUTES = int(setting("JWT_TTL_MINUTES", "60"))
RESET_TOKEN_TTL_MINUTES = int(setting("RESET_TOKEN_TTL_MINUTES", "30"))
RATE_LIMIT_PER_MINUTE = int(setting("RATE_LIMIT_PER_MINUTE", "60"))
WEATHER_PROVIDER_URL = setting("WEATHER_PROVIDER_URL")
WEATHER_PROVIDER_API_KEY = setting("WEATHER_PROVIDER_API_KEY")
WEATHER_CACHE_TTL_MINUTES = int(setting("WEATHER_CACHE_TTL_MINUTES", "30"))
WEATHER_TIMEOUT_SECONDS = float(setting("WEATHER_TIMEOUT_SECONDS", "5"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in setting("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]


def sqlite_path() -> Path:
    if DATABASE_URL.startswith("sqlite:///"):
        return Path(DATABASE_URL.removeprefix("sqlite:///"))
    return BACKEND_DIR / "database" / "agronexus.db"

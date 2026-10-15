"""Weather provider adapter with bounded retries, cache, freshness and fallback."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from config import WEATHER_CACHE_TTL_MINUTES, WEATHER_PROVIDER_API_KEY, WEATHER_PROVIDER_URL, WEATHER_TIMEOUT_SECONDS
from database.database import connect


def get_weather(latitude: float, longitude: float) -> dict[str, Any]:
    key = f"{latitude:.4f}:{longitude:.4f}"
    now = time.time()
    with connect() as db:
        cached = db.execute("SELECT payload, fetched_at FROM weather_cache WHERE cache_key = ?", (key,)).fetchone()
    if cached:
        age = now - float(cached["fetched_at"])
        if age <= WEATHER_CACHE_TTL_MINUTES * 60:
            return {**json.loads(cached["payload"]), "provider_status": "cached", "stale": False, "age_seconds": round(age)}

    if WEATHER_PROVIDER_URL:
        url = WEATHER_PROVIDER_URL + ("&" if "?" in WEATHER_PROVIDER_URL else "?") + urllib.parse.urlencode({"lat": latitude, "lon": longitude, "apikey": WEATHER_PROVIDER_API_KEY})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=WEATHER_TIMEOUT_SECONDS) as response:
                    payload = json.loads(response.read().decode())
                payload["fetched_at"] = datetime.now(timezone.utc).isoformat()
                with connect() as db:
                    db.execute("INSERT OR REPLACE INTO weather_cache(cache_key, payload, fetched_at) VALUES (?, ?, ?)", (key, json.dumps(payload), now))
                return {**payload, "provider_status": "live", "stale": False, "age_seconds": 0}
            except Exception:
                if attempt == 2:
                    break
                time.sleep(0.1 * (attempt + 1))

    fallback = {"temperature": 28.0, "humidity": 68.0, "rain_probability": 25.0, "fetched_at": datetime.now(timezone.utc).isoformat()}
    return {**fallback, "provider_status": "local_fallback", "estimated": True, "stale": True, "age_seconds": None}

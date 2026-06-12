"""Pre-LLM skill providers — jokes and weather (Phase 30).

Both skills run BEFORE the prompt is built, preserving the LLM-purity invariant
(no tool-calls, pure Russian text). They follow the same shape as echoes_gate:
intent is detected outside the LLM, then we either inject context (weather) or
short-circuit to a verbatim spoken reply (jokes).

- IntentRouter   — keyword classifier transcript -> "joke" | "weather" | None.
- WeatherProvider — background-cached fetch from Open-Meteo (direct egress).
- JokeGate       — verbatim selector over a curated pool with per-joke cooldown.
"""
from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .echoes_gate import EchoEntry, parse_echoes_file
from .memory import EpisodicMemory

log = logging.getLogger(__name__)


# ---------- Intent router ----------


class IntentRouter:
    """Classify a transcript into a skill intent by keyword — fully offline.

    LLM-based classification would double prefill latency (~9 s/turn on Gemma 4
    E4B SWA cache), so cheap substring matching is used instead. Matching is
    substring (not word-boundary) so stems like "погод" catch all inflections.
    Joke intent takes priority over weather when both match.
    """

    def __init__(self, *, joke_keywords: list[str], weather_keywords: list[str]) -> None:
        self._joke = [k.lower() for k in joke_keywords if k]
        self._weather = [k.lower() for k in weather_keywords if k]

    def classify(self, transcript: str) -> Optional[str]:
        if not transcript or not transcript.strip():
            return None
        text = transcript.lower()
        if any(k in text for k in self._joke):
            return "joke"
        if any(k in text for k in self._weather):
            return "weather"
        return None


# ---------- Weather ----------


# WMO weather interpretation codes → short Russian description.
# https://open-meteo.com/en/docs (WMO Weather interpretation codes WW)
_WMO_RU: dict[int, str] = {
    0: "ясно",
    1: "малооблачно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "слабая морось",
    53: "морось",
    55: "сильная морось",
    56: "ледяная морось",
    57: "сильная ледяная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    66: "ледяной дождь",
    67: "сильный ледяной дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "кратковременный дождь",
    81: "ливень",
    82: "сильный ливень",
    85: "снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}


@dataclass
class WeatherReading:
    fetched_at: float
    ctx_text: str


class WeatherProvider:
    """Background-cached weather for a fixed location.

    A long-lived poll_loop() refreshes the cache every poll_interval_sec; the
    dialogue turn only ever reads the cache (cached()), so no HTTP latency is
    added to the ~9 s LLM prefill.

    Network egress to api.open-meteo.com (an external HTTPS host, unlike the
    ESP32/localhost clients) is environment-dependent: on some networks direct
    egress works (trust_env=False, no proxy); on others ALL outbound traffic is
    routed through the local v2ray proxy (CLAUDE.md gotcha, 127.0.0.1:10808) and
    direct egress times out. fetch_once() tries direct egress first, then falls
    back to skills.weather.fallback_proxy_url — so the skill works on both kinds
    of network without reconfiguration.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "https://api.open-meteo.com/v1/forecast"))
        self.latitude = float(config.get("latitude", 0.0))
        self.longitude = float(config.get("longitude", 0.0))
        self.location_name = str(config.get("location_name", "") or "")
        self.poll_interval = int(config.get("poll_interval_sec", 900))
        self.cache_ttl = int(config.get("cache_ttl_sec", 1800))
        self.timeout = int(config.get("timeout_sec", 8))
        self.fallback_proxy_url = str(config.get("fallback_proxy_url", "") or "")
        self._lock = threading.Lock()
        self._reading: Optional[WeatherReading] = None

    async def fetch_once(self) -> Optional[WeatherReading]:
        """Fetch + cache one reading. Returns None on any failure (silent-safe)."""
        import httpx  # lazy — keeps module import cheap on non-network hosts

        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "wind_speed_unit": "ms",
            "timezone": "auto",
        }
        # Direct egress first; if the network only routes out via v2ray, the
        # fallback proxy variant picks it up. Either path ignores trust_env so
        # neither leaks ESP32/localhost traffic into v2ray (CLAUDE.md gotcha).
        client_variants: list[dict[str, Any]] = [{"trust_env": False}]
        if self.fallback_proxy_url:
            client_variants.append({"trust_env": False, "proxy": self.fallback_proxy_url})

        data: Any = None
        last_exc: Exception | None = None
        for kwargs in client_variants:
            try:
                async with httpx.AsyncClient(timeout=self.timeout, **kwargs) as client:
                    resp = await client.get(self.base_url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                break
            except Exception as exc:  # network/parse — try next variant
                last_exc = exc
                continue

        if data is None:  # all variants failed — never raise into the turn
            log.warning("weather fetch failed: %s", last_exc)
            return None
        reading = self._format(data)
        if reading is not None:
            with self._lock:
                self._reading = reading
            log.info("weather updated: %s", reading.ctx_text)
        return reading

    @staticmethod
    def _format(data: dict[str, Any]) -> Optional[WeatherReading]:
        current = data.get("current") if isinstance(data, dict) else None
        if not isinstance(current, dict) or "temperature_2m" not in current:
            return None
        try:
            temp = round(float(current["temperature_2m"]))
        except (TypeError, ValueError):
            return None
        code = int(current.get("weather_code", 0) or 0)
        desc = _WMO_RU.get(code, "")
        sign = "+" if temp > 0 else ""
        parts = [f"{sign}{temp}°"]
        if desc:
            parts.append(desc)
        wind = current.get("wind_speed_10m")
        if wind is not None:
            try:
                parts.append(f"ветер {round(float(wind))} м/с")
            except (TypeError, ValueError):
                pass
        return WeatherReading(fetched_at=time.time(), ctx_text=", ".join(parts))

    def cached(self) -> Optional[str]:
        """Return the cached weather string, or None if missing/stale."""
        with self._lock:
            reading = self._reading
        if reading is None:
            return None
        if time.time() - reading.fetched_at > self.cache_ttl:
            return None
        return reading.ctx_text

    async def poll_loop(self) -> None:
        """Long-lived background task. Cancelled on orchestrator shutdown."""
        while True:
            try:
                await self.fetch_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # defensive — loop must never die
                log.warning("weather poll_loop error: %s", exc)
            await asyncio.sleep(max(60, self.poll_interval))


# ---------- Jokes ----------


class JokeGate:
    """Verbatim joke selector over a curated pool.

    Reuses the Echoes file format (yaml-frontmatter blocks parsed by
    echoes_gate.parse_echoes_file) and the EpisodicMemory cooldown store
    (pool="jokes" → data/adam/jokes_used.jsonl). Unlike EchoGate, selection is
    NOT tag-matched against the transcript — the intent is already known, so we
    just pick a random eligible (not-on-cooldown) joke.
    """

    def __init__(
        self,
        *,
        pool_path: str | Path,
        memory: EpisodicMemory,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.pool_path = Path(pool_path)
        self.memory = memory
        self._rng = rng or random.Random()
        self._lock = threading.RLock()
        self._mtime: float = 0.0
        self._entries: list[EchoEntry] = []
        self.reload()

    def reload(self) -> int:
        """Reload the pool if the file changed on disk. Returns entry count."""
        with self._lock:
            try:
                mtime = self.pool_path.stat().st_mtime
            except FileNotFoundError:
                self._entries = []
                self._mtime = 0.0
                return 0
            if mtime == self._mtime and self._entries:
                return len(self._entries)
            self._entries = parse_echoes_file(self.pool_path, pool="jokes")
            self._mtime = mtime
            log.info("joke_gate: loaded %d jokes", len(self._entries))
            return len(self._entries)

    def pick(self, *, cooldown_days: int = 3, now: Optional[datetime] = None) -> Optional[EchoEntry]:
        """Choose one eligible joke and record its use. None if the pool is empty.

        Side-effect: records the chosen joke's use for cooldown tracking.
        If every joke is on cooldown, falls back to the full pool (a repeat is
        better than silence on an explicit request).
        """
        self.reload()
        with self._lock:
            entries = list(self._entries)
        if not entries:
            return None
        now = now or datetime.now(timezone.utc)
        eligible = entries
        if cooldown_days > 0:
            cutoff = now - timedelta(days=cooldown_days)
            recent = self.memory.all_recent_uses(pool="jokes", since=cutoff)
            filtered = [e for e in entries if e.id not in recent]
            if filtered:
                eligible = filtered
        chosen = self._rng.choice(eligible)
        self.memory.record_echo_used(chosen.id, pool="jokes")
        return chosen

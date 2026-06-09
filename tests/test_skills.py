"""Tests for Phase 30 skills — IntentRouter, WeatherProvider, JokeGate.

Network is never touched: WeatherProvider.fetch_once imports httpx lazily, so
these tests inject a fake httpx module into sys.modules for the success/failure
paths. Everything else is pure-Python and deterministic.
"""
from __future__ import annotations

import asyncio
import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "System"))

from adam.memory import EpisodicMemory  # noqa: E402
from adam.skills import IntentRouter, JokeGate, WeatherProvider  # noqa: E402


# ─── IntentRouter ────────────────────────────────────────────────────────────

def _router() -> IntentRouter:
    return IntentRouter(
        joke_keywords=["пошути", "анекдот", "шутк"],
        weather_keywords=["погод", "на улице", "градус"],
    )


def test_intent_joke():
    assert _router().classify("Адам, пошути!") == "joke"
    assert _router().classify("расскажи анекдот") == "joke"


def test_intent_weather():
    assert _router().classify("какая сегодня погода?") == "weather"
    assert _router().classify("сколько градусов на улице") == "weather"


def test_intent_none_and_empty():
    assert _router().classify("как тебя зовут?") is None
    assert _router().classify("") is None
    assert _router().classify("   ") is None


def test_intent_case_insensitive():
    assert _router().classify("ПОШУТИ давай") == "joke"


def test_intent_joke_priority_over_weather():
    # transcript containing both → joke wins (explicit request beats ambient)
    assert _router().classify("пошути про погоду") == "joke"


# ─── WeatherProvider formatting ──────────────────────────────────────────────

def _wp() -> WeatherProvider:
    return WeatherProvider({
        "base_url": "http://example/forecast",
        "latitude": 55.7,
        "longitude": 37.6,
        "cache_ttl_sec": 1800,
        "timeout_sec": 5,
    })


def test_weather_format_positive():
    r = WeatherProvider._format({"current": {"temperature_2m": 3.4, "weather_code": 3, "wind_speed_10m": 5.1}})
    assert r is not None
    assert r.ctx_text == "+3°, пасмурно, ветер 5 м/с"


def test_weather_format_negative_temp():
    r = WeatherProvider._format({"current": {"temperature_2m": -7.0, "weather_code": 71, "wind_speed_10m": 2}})
    assert r.ctx_text == "-7°, небольшой снег, ветер 2 м/с"


def test_weather_format_unknown_code_no_wind():
    r = WeatherProvider._format({"current": {"temperature_2m": 0.2, "weather_code": 999}})
    # unknown code → no description; no wind field → no wind clause; 0° → no sign
    assert r.ctx_text == "0°"


def test_weather_format_missing_temp_returns_none():
    assert WeatherProvider._format({"current": {"weather_code": 1}}) is None
    assert WeatherProvider._format({}) is None
    assert WeatherProvider._format({"current": "garbage"}) is None


# ─── WeatherProvider cache TTL ───────────────────────────────────────────────

def test_weather_cached_none_when_empty():
    assert _wp().cached() is None


def test_weather_cached_fresh_and_stale():
    wp = _wp()
    from adam.skills import WeatherReading
    wp._reading = WeatherReading(fetched_at=time.time(), ctx_text="+1°, ясно")
    assert wp.cached() == "+1°, ясно"
    # age it past TTL
    wp._reading.fetched_at = time.time() - 1801
    assert wp.cached() is None


# ─── WeatherProvider.fetch_once with a fake httpx ────────────────────────────

class _FakeResp:
    def __init__(self, data, raise_exc=None):
        self._data = data
        self._raise = raise_exc

    def raise_for_status(self):
        if self._raise:
            raise self._raise

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, data=None, exc=None, **kwargs):
        self._data = data
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        if self._exc:
            raise self._exc
        return _FakeResp(self._data)


def _install_fake_httpx(monkeypatch, *, data=None, exc=None):
    fake = types.ModuleType("httpx")
    fake.AsyncClient = lambda **kwargs: _FakeClient(data=data, exc=exc, **kwargs)
    monkeypatch.setitem(sys.modules, "httpx", fake)


def test_weather_fetch_once_success(monkeypatch):
    _install_fake_httpx(monkeypatch, data={"current": {"temperature_2m": 10.0, "weather_code": 0, "wind_speed_10m": 1}})
    wp = _wp()
    reading = asyncio.run(wp.fetch_once())
    assert reading is not None
    assert reading.ctx_text == "+10°, ясно, ветер 1 м/с"
    # cached now returns it
    assert wp.cached() == "+10°, ясно, ветер 1 м/с"


def test_weather_fetch_once_network_error_returns_none(monkeypatch):
    _install_fake_httpx(monkeypatch, exc=RuntimeError("boom"))
    wp = _wp()
    assert asyncio.run(wp.fetch_once()) is None
    assert wp.cached() is None  # failed fetch leaves cache empty


# ─── JokeGate ────────────────────────────────────────────────────────────────

_POOL = """# jokes
```yaml
---
id: j1
---
```
Первый анекдот.

---

```yaml
---
id: j2
---
```
Второй анекдот.

---

```yaml
---
id: j3
---
```
Третий анекдот.
"""


def _joke_gate(tmp_path: Path):
    pool = tmp_path / "Jokes.md"
    pool.write_text(_POOL, encoding="utf-8")
    mem = EpisodicMemory(tmp_path / "data")
    import random
    return JokeGate(pool_path=pool, memory=mem, rng=random.Random(42)), mem


def test_joke_gate_loads_pool(tmp_path):
    jg, _ = _joke_gate(tmp_path)
    assert len(jg._entries) == 3


def test_joke_gate_pick_records_use(tmp_path):
    jg, mem = _joke_gate(tmp_path)
    j = jg.pick(cooldown_days=3)
    assert j is not None
    recent = mem.all_recent_uses(pool="jokes")
    assert j.id in recent


def test_joke_gate_cooldown_avoids_repeats(tmp_path):
    jg, _ = _joke_gate(tmp_path)
    picks = {jg.pick(cooldown_days=3).id for _ in range(3)}
    assert picks == {"j1", "j2", "j3"}  # all three before any repeat


def test_joke_gate_cooldown_zero_allows_repeat(tmp_path):
    jg, _ = _joke_gate(tmp_path)
    # with cooldown disabled, the seeded rng may repeat freely; just ensure no crash
    ids = [jg.pick(cooldown_days=0).id for _ in range(10)]
    assert all(i in {"j1", "j2", "j3"} for i in ids)


def test_joke_gate_empty_pool(tmp_path):
    pool = tmp_path / "Empty.md"
    pool.write_text("# nothing here\n", encoding="utf-8")
    mem = EpisodicMemory(tmp_path / "data")
    jg = JokeGate(pool_path=pool, memory=mem)
    assert jg.pick(cooldown_days=3) is None

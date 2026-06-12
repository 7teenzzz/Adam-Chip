"""Integration tests — Phase 30 weather pipeline.

Tests the full path:
  network → WeatherProvider.fetch_once()
           → cached()
           → IntentRouter.classify()
           → PromptBuilder injection
           → [ctx.weather] in LLM messages

Requires:
  - httpx installed: pip install httpx
  - Network access to api.open-meteo.com (direct egress, no proxy)

Run on Jetson:
  pytest tests/test_weather_integration.py -v -s

Skip in offline CI:
  pytest tests/ --ignore=tests/test_weather_integration.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "System"))

# Load real production config — tests exercise the actual configured values,
# not hardcoded copies that can drift.
_CFG_PATH = ROOT / "System" / "Config.json"
with _CFG_PATH.open(encoding="utf-8") as _f:
    _CFG = json.load(_f)

_WEATHER_CFG = _CFG["skills"]["weather"]
_JOKE_CFG = _CFG["skills"]["jokes"]

from adam.skills import IntentRouter, WeatherProvider  # noqa: E402
from adam.prompt import PromptBuilder  # noqa: E402


# ─── 1. Сеть: прямой доступ к Open-Meteo ─────────────────────────────────────

def _open_meteo_get(httpx_mod, params: dict) -> "httpx.Response":
    """GET base_url, trying direct egress then fallback_proxy_url.

    Mirrors WeatherProvider.fetch_once(): some hosts have open internet
    (trust_env=False, no proxy), others route all outbound traffic through
    the local v2ray proxy (CLAUDE.md gotcha, 127.0.0.1:10808) and direct
    egress times out. Tries direct first, falls back to the proxy.
    """
    timeout = _WEATHER_CFG["timeout_sec"]
    last_exc: Exception | None = None
    for kwargs in (
        {"trust_env": False},
        {"trust_env": False, "proxy": _WEATHER_CFG.get("fallback_proxy_url") or None},
    ):
        if kwargs.get("proxy") is None and "proxy" in kwargs:
            continue
        try:
            with httpx_mod.Client(timeout=timeout, **kwargs) as c:
                return c.get(_WEATHER_CFG["base_url"], params=params)
        except Exception as exc:
            last_exc = exc
            continue
    raise last_exc  # type: ignore[misc]


def test_open_meteo_reachable():
    """api.open-meteo.com доступен напрямую или через fallback_proxy_url."""
    httpx = pytest.importorskip("httpx", reason="httpx не установлен")
    params = {
        "latitude": _WEATHER_CFG["latitude"],
        "longitude": _WEATHER_CFG["longitude"],
        "current": "temperature_2m",
        "timezone": "auto",
    }
    r = _open_meteo_get(httpx, params)
    print(f"\n  HTTP {r.status_code}  {r.url}")
    assert r.status_code == 200, f"Ожидали 200, получили {r.status_code}:\n{r.text[:300]}"


def test_open_meteo_response_shape():
    """Open-Meteo возвращает корректную структуру с полем current.temperature_2m."""
    httpx = pytest.importorskip("httpx", reason="httpx не установлен")
    params = {
        "latitude": _WEATHER_CFG["latitude"],
        "longitude": _WEATHER_CFG["longitude"],
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "wind_speed_unit": "ms",
        "timezone": "auto",
    }
    data = _open_meteo_get(httpx, params).json()
    current = data.get("current", {})
    print(f"\n  current: {current}")
    assert "temperature_2m" in current, f"Нет temperature_2m в ответе: {current}"
    assert "weather_code" in current, f"Нет weather_code в ответе: {current}"
    assert isinstance(current["temperature_2m"], (int, float)), \
        f"temperature_2m не число: {current['temperature_2m']!r}"


# ─── 2. WeatherProvider.fetch_once() ─────────────────────────────────────────

def test_weather_fetch_once_returns_reading():
    """fetch_once() возвращает WeatherReading с непустым ctx_text."""
    pytest.importorskip("httpx", reason="httpx не установлен")
    wp = WeatherProvider(_WEATHER_CFG)
    reading = asyncio.run(wp.fetch_once())
    assert reading is not None, (
        "fetch_once() вернул None — сеть недоступна или httpx не установлен"
    )
    assert reading.ctx_text, "ctx_text пустой"
    assert "°" in reading.ctx_text, f"Нет символа градуса: {reading.ctx_text!r}"
    print(f"\n  ctx_text:   {reading.ctx_text!r}")
    print(f"  fetched_at: {reading.fetched_at:.1f}")


def test_weather_fetch_populates_cache():
    """После fetch_once() метод cached() возвращает ту же строку."""
    pytest.importorskip("httpx", reason="httpx не установлен")
    wp = WeatherProvider(_WEATHER_CFG)
    reading = asyncio.run(wp.fetch_once())
    assert reading is not None
    cached = wp.cached()
    assert cached is not None, "cached() вернул None после успешного fetch"
    assert cached == reading.ctx_text, (
        f"cached() вернул другую строку:\n  fetch:  {reading.ctx_text!r}\n  cached: {cached!r}"
    )
    print(f"\n  cached: {cached!r}")


def test_weather_ctx_text_format():
    """ctx_text соответствует формату «±T°[, описание][, ветер N м/с]»."""
    pytest.importorskip("httpx", reason="httpx не установлен")
    wp = WeatherProvider(_WEATHER_CFG)
    reading = asyncio.run(wp.fetch_once())
    assert reading is not None
    text = reading.ctx_text
    # Температура должна быть первым элементом
    first = text.split(",")[0].strip()
    assert first.endswith("°"), f"Первый элемент не температура: {first!r} в {text!r}"
    # Если есть ветер — содержит «м/с»
    if "ветер" in text:
        assert "м/с" in text, f"Ветер без единиц м/с: {text!r}"
    print(f"\n  ctx_text: {text!r}  — формат OK")


# ─── 3. IntentRouter — production keywords ───────────────────────────────────

def test_intent_all_weather_keywords_from_config():
    """Все intent_keywords из Config.json.skills.weather детектируются корректно."""
    router = IntentRouter(
        joke_keywords=list(_JOKE_CFG["intent_keywords"]),
        weather_keywords=list(_WEATHER_CFG["intent_keywords"]),
    )
    # Фразы, содержащие каждое ключевое слово из конфига
    samples = [
        ("погода", "какая сегодня погода?"),
        ("на улице", "холодно ли на улице?"),
        ("за окном", "что происходит за окном"),
        ("холодно", "очень холодно сегодня"),
        ("тепло", "тепло на улице"),
        ("жарко", "жарко на улице?"),
        ("дожд", "идёт дождь?"),
        ("снег", "снег идёт?"),
        ("ветер", "сильный ветер?"),
        ("градус", "сколько градусов?"),
    ]
    for kw, phrase in samples:
        result = router.classify(phrase)
        assert result == "weather", (
            f"keyword={kw!r} phrase={phrase!r} → ожидали 'weather', получили {result!r}"
        )
    print(f"\n  Все {len(samples)} keywords детектируются корректно")


def test_intent_joke_priority_over_weather():
    """При совпадении joke + weather — побеждает joke (приоритет)."""
    router = IntentRouter(
        joke_keywords=list(_JOKE_CFG["intent_keywords"]),
        weather_keywords=list(_WEATHER_CFG["intent_keywords"]),
    )
    assert router.classify("пошути про погоду") == "joke"
    assert router.classify("расскажи анекдот про дождь") == "joke"


def test_intent_no_false_positives_on_neutral():
    """Обычные реплики не классифицируются как weather-интент."""
    router = IntentRouter(
        joke_keywords=list(_JOKE_CFG["intent_keywords"]),
        weather_keywords=list(_WEATHER_CFG["intent_keywords"]),
    )
    for phrase in ["привет", "кто ты?", "ты живой?", "расскажи о себе", "", "   "]:
        result = router.classify(phrase)
        assert result is None, f"Ложное срабатывание на {phrase!r}: {result!r}"


# ─── 4. PromptBuilder — [ctx.weather] инжекция ───────────────────────────────

def test_prompt_weather_block_present():
    """PromptBuilder.build_messages() вставляет [ctx.weather] при наличии ctx."""
    builder = PromptBuilder(persona_paths=[], history_turns=0)
    weather_str = "+5°, пасмурно, ветер 3 м/с"
    messages = builder.build_messages(
        transcript="какая погода?",
        dialogue_history=[],
        scene_cache="",
        sensors={},
        weather_ctx=weather_str,
        include_scene=False,
        include_sensors=False,
    )
    ctx_msg = next(
        (m for m in messages if "[ctx.weather]" in m.get("content", "")), None
    )
    assert ctx_msg is not None, (
        "Блок [ctx.weather] отсутствует в сообщениях промпта\n"
        f"messages: {[m['role'] for m in messages]}"
    )
    assert weather_str in ctx_msg["content"], (
        f"ctx_text не найден в блоке:\n{ctx_msg['content']}"
    )
    print(f"\n  role={ctx_msg['role']!r}")
    print(f"  content:\n{ctx_msg['content']}")


def test_prompt_no_weather_block_without_ctx():
    """Без weather_ctx блок [ctx.weather] НЕ попадает в промпт."""
    builder = PromptBuilder(persona_paths=[], history_turns=0)
    messages = builder.build_messages(
        transcript="кто ты?",
        dialogue_history=[],
        scene_cache="",
        sensors={},
        include_scene=False,
        include_sensors=False,
    )
    leaked = [m for m in messages if "[ctx.weather]" in m.get("content", "")]
    assert not leaked, (
        "Блок [ctx.weather] появился без weather_ctx — утечка контекста\n"
        f"leaked: {leaked}"
    )


def test_prompt_weather_block_position():
    """[ctx.weather] находится в system-сообщении, а не в user."""
    builder = PromptBuilder(persona_paths=[], history_turns=0)
    messages = builder.build_messages(
        transcript="погода?",
        dialogue_history=[],
        scene_cache="",
        sensors={},
        weather_ctx="+2°, снег",
        include_scene=False,
        include_sensors=False,
    )
    ctx_msg = next(
        (m for m in messages if "[ctx.weather]" in m.get("content", "")), None
    )
    assert ctx_msg is not None
    assert ctx_msg["role"] == "system", (
        f"[ctx.weather] должен быть в system, а не в {ctx_msg['role']!r}"
    )


# ─── 5. E2E: fetch → интент → промпт ─────────────────────────────────────────

def test_e2e_weather_fetch_to_llm_prompt():
    """E2E: реальный HTTP → ctx_text → IntentRouter → PromptBuilder → в промпте."""
    pytest.importorskip("httpx", reason="httpx не установлен")

    # Шаг 1: получить погоду
    wp = WeatherProvider(_WEATHER_CFG)
    reading = asyncio.run(wp.fetch_once())
    assert reading is not None, "Нет данных о погоде — проверь сеть"
    weather_str = wp.cached()
    assert weather_str is not None

    # Шаг 2: распознать интент
    router = IntentRouter(
        joke_keywords=list(_JOKE_CFG["intent_keywords"]),
        weather_keywords=list(_WEATHER_CFG["intent_keywords"]),
    )
    intent = router.classify("что сейчас на улице?")
    assert intent == "weather", f"Интент не распознан: {intent!r}"

    # Шаг 3: собрать промпт
    builder = PromptBuilder(persona_paths=[], history_turns=0)
    messages = builder.build_messages(
        transcript="что сейчас на улице?",
        dialogue_history=[],
        scene_cache="",
        sensors={},
        weather_ctx=weather_str,
        include_scene=False,
        include_sensors=False,
    )

    # Шаг 4: проверить что [ctx.weather] в промпте
    ctx_msg = next(
        (m for m in messages if "[ctx.weather]" in m.get("content", "")), None
    )
    assert ctx_msg is not None, "E2E: [ctx.weather] не попал в промпт"
    assert weather_str in ctx_msg["content"]

    print(f"\n  E2E OK")
    print(f"  weather: {weather_str!r}")
    print(f"  intent:  {intent!r}")
    print(f"  prompt block:\n{ctx_msg['content']}")

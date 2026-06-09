# Phase 30: Skills — Jokes + Weather (pre-LLM providers)

**Gathered:** 2026-06-07
**Status:** Implemented, pending Jetson smoke-test + commit

<domain>
## Phase Boundary

Два новых навыка, работающих **до** построения LLM-промпта — сохраняет инвариант «LLM = чистый русский текст» (никаких tool-calls):

**JokeGate** — при явном запросе пошутить выбирает один анекдот из курированного пула `Agent-Adam-Chip/About/Jokes.md` и произносит его **verbatim через TTS, минуя LLM**. Цель: пунчлайн не «плывёт» после прохождения через Gemma 4 E4B (~9 с SWA-cache prefill сэкономлены).

**WeatherProvider** — фоновый воркер опрашивает Open-Meteo API раз в 15 минут, кэширует строку вида `+3°, пасмурно, ветер 5 м/с`. На weather-intent тёрне строка инжектируется как `[ctx.weather]` в промпт — Адам говорит в образе. При протухшем/отсутствующем кэше инжектируется `"(датчик улицы сейчас недоступен)"` → Адам всё равно отвечает (инвариант: action failure ≠ silence).

**In scope:** IntentRouter (offline keyword classifier), WeatherProvider (Open-Meteo, direct egress, trust_env=False), JokeGate (verbatim selector, cooldown через EpisodicMemory pool="jokes"), инжекция `[ctx.weather]` в PromptBuilder, Config.json секция `skills.*`, пул 25 анекдотов, unit-тесты (18 шт.), интеграционные тесты (12 шт.).

**Out of scope:** LLM-based intent (слишком медленно), TTS-управление темпом/паузами анекдота, расширение weather-данных (осадки, УФ-индекс), динамическое обновление пула анекдотов из UI.
</domain>

<decisions>
## Implementation Decisions

### D-01: Pre-LLM, не post-LLM
Оба навыка детектируют интент и выполняются ДО вызова LLM. Альтернатива (LLM tool-calls) нарушила бы инвариант «LLM = чистый текст» + добавила ~9 с latency на каждый навык-тёрн. Паттерн: если `intent == "joke"` → shortcut-функция `_run_joke_turn()`, LLM не вызывается; если `intent == "weather"` → строка в `weather_ctx`, LLM получает контекст как `[ctx.weather]`.

### D-02: JokeGate — verbatim, не LLM-перефраз
Анекдоты произносятся дословно из файла. LLM-перефраз ломает пунчлайн («Я говорю из опыта» → «Мне кажется, это опасно»). Трейд-офф: Адам иногда звучит «по-другому», чем обычно, — приемлемо для явного навыка.

### D-03: Cooldown через EpisodicMemory pool="jokes"
`EpisodicMemory.record_echo_used()` / `all_recent_uses()` принимают произвольный pool-name. Переиспользован без изменений с `pool="jokes"`. Default cooldown = 3 дня (настраивается через `skills.jokes.per_joke_cooldown_days`). При исчерпании пула (всё на cooldown) — fallback на весь пул (повтор лучше молчания на явный запрос).

### D-04: WeatherProvider — trust_env=False, прямой egress
v2ray (порт 10808) перехватывает `urllib`/`httpx` без `trust_env=False`. Для ESP32/localhost используем `_NO_PROXY_OPENER` (NO_PROXY). Для Open-Meteo (внешний сервис) нужен **прямой** интернет — `httpx.AsyncClient(trust_env=False)` игнорирует proxy-переменные полностью. Противоположная логика, тот же флаг.

### D-05: httpx — lazy import
`import httpx` внутри `fetch_once()`, не на уровне модуля. Причина: на dev-машине без httpx модуль `skills.py` импортируется без ошибки. Тесты мокают `sys.modules["httpx"]` напрямую.

### D-06: Формат пула анекдотов = Echoes.md
Переиспользован существующий YAML-frontmatter формат (`echoes_gate.parse_echoes_file`). Теги опциональны и не используются gate'ом (выбор случайный среди eligible). Это позволяет не писать новый парсер и сохранить совместимость с будущими инструментами, работающими с Echoes.

### D-07: Пул — 25 анекдотов, куратирован автором
Анекдоты написаны/одобрены автором проекта. Темы: экзистенциальный юмор, AI-самосознание, тёмная ирония. Характер: короткие (1–3 предложения), без эмодзи, на русском. Список финализирован в этой ветке.

### D-08: Joke фрейм — случайный из пула
Перед анекдотом произносится случайная короткая фраза-фрейм (`_JOKE_FRAMES = ["Лови.", "Держи.", "Хочешь? Слушай.", ...]`, включая пустую строку). Снижает монотонность повторных запросов.
</decisions>

<canonical_refs>
## Canonical References

**Следующий агент ОБЯЗАН прочитать перед работой с этой фазой.**

### Новые файлы (Phase 30)
- `System/adam/skills.py` — IntentRouter, WeatherProvider (_WMO_RU dict, _format, cached, poll_loop), JokeGate
- `Agent-Adam-Chip/About/Jokes.md` — пул 25 анекдотов (формат Echoes.md, pool="jokes")
- `tests/test_skills.py` — 18 unit-тестов (IntentRouter, WeatherProvider format/cache/fetch, JokeGate cooldown)
- `tests/test_weather_integration.py` — 12 интеграционных тестов (сеть, full pipeline, E2E)

### Изменённые файлы
- `System/Orchestrator.py` — импорт IntentRouter/JokeGate/WeatherProvider; weather poll_loop в lifespan(); intent-врезка в `_run_dialogue_turn_locked`; новая функция `_run_joke_turn()`
- `System/adam/prompt.py` — `build_messages()` + `_build_context_body()` принимают `weather_ctx: Optional[str]`; инжекция `[ctx.weather]` блока
- `System/Config.json` — секция `skills.weather` (координаты Галереи А-Б: 55.721265, 37.625647) + `skills.jokes`
- `System/Config.schema.json` — документация `skills.*` со всеми полями
- `System/adam/config.py` — DEFAULT_CONFIG секция `skills`

### Паттерны для понимания
- `System/adam/echoes_gate.py` — EchoEntry, parse_echoes_file(), EchoGate (образец для JokeGate)
- `System/adam/memory.py` — `record_echo_used(id, pool)`, `all_recent_uses(pool, since)` (cooldown infrastructure, переиспользована без изменений)
- `System/adam/prompt.py` — паттерн `[ctx.X]` блоков (vision, sensors, memory — weather добавлен аналогично)

### Конфиг-параметры (Config-First)
```json
"skills": {
  "weather": {
    "enabled": true,
    "provider": "open_meteo",
    "base_url": "https://api.open-meteo.com/v1/forecast",
    "latitude": 55.721265,
    "longitude": 37.625647,
    "location_name": "Москва",
    "poll_interval_sec": 900,
    "cache_ttl_sec": 1800,
    "timeout_sec": 8,
    "intent_keywords": ["погод","на улице","за окном","холодно","тепло","жарко","дожд","снег","ветер","градус"]
  },
  "jokes": {
    "enabled": true,
    "pool_path": "Agent-Adam-Chip/About/Jokes.md",
    "per_joke_cooldown_days": 3,
    "intent_keywords": ["пошути","анекдот","рассмеши","шутк","смешн","развесели"]
  }
}
```
</canonical_refs>

<testing>
## Testing

### Unit-тесты (offline, без сети)
```bash
pytest tests/test_skills.py -v
# 18 passed
```
Покрывают: IntentRouter (все ветки + приоритеты), WeatherProvider._format() (форматы температуры, WMO коды, отсутствующие поля), WeatherProvider кэш TTL, fetch_once с fake httpx (успех + network error), JokeGate (загрузка пула, выбор, cooldown, пустой пул).

### Интеграционные тесты (требуют сеть + httpx)
```bash
# Установить httpx на Jetson (если ещё нет):
pip install httpx

# Запустить на Jetson:
pytest tests/test_weather_integration.py -v -s
```

**Что проверяют (12 тестов, 5 групп):**

1. **Сеть** (`test_open_meteo_reachable`, `test_open_meteo_response_shape`) — HTTP 200 от `api.open-meteo.com` без прокси (`trust_env=False`); структура JSON содержит `current.temperature_2m`, `weather_code`, `wind_speed_10m`.

2. **WeatherProvider** (`test_weather_fetch_once_returns_reading`, `test_weather_fetch_populates_cache`, `test_weather_ctx_text_format`) — `fetch_once()` возвращает `WeatherReading` с `°`, кэш после fetch не None, формат строки соответствует `±T°[, описание][, ветер N м/с]`.

3. **IntentRouter** (`test_intent_all_weather_keywords_from_config`, `test_intent_joke_priority_over_weather`, `test_intent_no_false_positives_on_neutral`) — читает реальный Config.json, проверяет все 10 weather-ключевых слов, приоритет joke над weather, отсутствие ложных срабатываний.

4. **PromptBuilder** (`test_prompt_weather_block_present`, `test_prompt_no_weather_block_without_ctx`, `test_prompt_weather_block_position`) — `[ctx.weather]` присутствует при наличии ctx, отсутствует без него, находится в role=system.

5. **E2E** (`test_e2e_weather_fetch_to_llm_prompt`) — весь тракт одним тестом: реальный HTTP → WeatherReading → IntentRouter → PromptBuilder → `[ctx.weather]` в итоговом списке messages.

### Smoke-тест на живом оркестраторе
```bash
# Запустить оркестратор, затем:
curl -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Адам, пошути"}' | python3 -m json.tool

curl -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"какая погода на улице?"}' | python3 -m json.tool
```
Ожидаемое: в первом ответе `skill="joke"`, reply = verbatim анекдот; во втором — `[ctx.weather]` в prompt_trace (если `trace_prompts=true`), reply содержит температуру.

### Известный pre-existing failure (не наш)
`tests/test_memory.py::test_semantic_roundtrip` — падает с `AttributeError: 'EpisodicMemory' object has no attribute 'write_semantic'`. Существовал до Phase 30, не связан с изменениями этой фазы.
</testing>

<code_context>
## Existing Code Insights

### Переиспользованная инфраструктура
- `parse_echoes_file(path, pool)` из `echoes_gate.py` — парсит YAML-frontmatter блоки; JokeGate вызывает без изменений
- `EpisodicMemory.record_echo_used(id, pool)` / `all_recent_uses(pool, since)` — cooldown store; Phase 30 добавляет `pool="jokes"` namespace
- `[ctx.X]` инжекция в `_build_context_body()` — weather добавлен по той же схеме, что vision/sensors/memory

### Интеграция в Orchestrator
Врезка intent-классификации в `_run_dialogue_turn_locked`, после echo/chinese gate блока, перед semantic memory:

```python
weather_ctx: str | None = None
intent = intent_router.classify(transcript)
if intent == "joke" and bool(_jokes_cfg.get("enabled", False)):
    joke = joke_gate.pick(cooldown_days=int(_jokes_cfg.get("per_joke_cooldown_days", 3)))
    if joke is not None:
        return await _run_joke_turn(...)  # LLM bypassed
elif intent == "weather" and bool(_weather_cfg.get("enabled", False)):
    weather_ctx = weather_provider.cached() or "(датчик улицы сейчас недоступен)"
```

### Зависимость httpx на Jetson
`httpx` — новая зависимость. Lazy import в `WeatherProvider.fetch_once()`. При первом запуске оркестратора на Jetson: `pip install httpx` если ещё нет.
</code_context>

<deferred>
## Deferred

- **TTS-пунктуация анекдотов** — выдержки паузы между setup и пунчлайном. Silero произносит ровно, без актёрских пауз. Возможно через `...` или явные паузы в тексте пула.
- **Расширение weather-данных** — осадки (precipitation), ощущаемая температура (apparent_temperature), UV-индекс. Пока минимум.
- **UI для управления пулом анекдотов** — редактирование Jokes.md через WebUI (аналогично Echoes). Не нужно для выставки.
- **Метрика joke/weather intent hits** — счётчики в events.jsonl. Сейчас: `skill_weather` событие логируется, joke логируется через `_run_joke_turn`. Агрегация в MetricsPanel не реализована.
- **Динамический пул** — hotreload Jokes.md без перезапуска. JokeGate.reload() вызывается на каждый pick() через mtime-check, т.е. уже работает по факту.
</deferred>

---

*Phase: 30-skills-jokes-weather*
*Context gathered: 2026-06-07*
*Branch: Extra (diverged from main @ 070ab4b)*

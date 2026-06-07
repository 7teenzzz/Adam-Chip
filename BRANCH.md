# Branch: Extra

**Diverged from:** main @ 070ab4b
**Goal:** Phase 30 — навыки jokes + weather (pre-LLM провайдеры: шутки verbatim, погода Open-Meteo)
**Status:** ready-for-review
**Merge target:** main
**Merge conditions:** smoke-тест на Jetson (`curl .../api/agent/turn` с «пошути» и «погода»), 18/18 тестов зелёные

**Modified areas:**

- `System/adam/skills.py` *(новый)* — IntentRouter, WeatherProvider, JokeGate
- `System/Orchestrator.py` — импорт skills, weather poll-loop в lifespan, intent-врезка в turn
- `System/adam/prompt.py` — параметр `weather_ctx`, блок `[ctx.weather]`
- `System/adam/config.py` — DEFAULT_CONFIG секция `skills`
- `System/Config.json` — секция `skills.weather` (координаты Галереи А-Б) + `skills.jokes`
- `System/Config.schema.json` — документация `skills.*`
- `Agent-Adam-Chip/About/Jokes.md` *(новый)* — пул 25 анекдотов для JokeGate
- `tests/test_skills.py` *(новый)* — 18 тестов

**Global changes:** да — добавлена секция `skills` в Config.json; при мёрже убедиться, что `httpx` установлен в venv на Jetson (`pip install httpx`)

**Notes for agents:**

- Оба навыка работают **до** сборки prompt: joke → verbatim TTS минуя LLM; weather → `[ctx.weather]` блок в prompt
- WeatherProvider: `trust_env=False` (прямой egress, игнорирует v2ray)
- JokeGate: переиспользует `EpisodicMemory.record_echo_used(pool="jokes")` для cooldown
- Pre-existing failure: `tests/test_memory.py::test_semantic_roundtrip` — не наша ветка

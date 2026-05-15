# Phase 1: Doc Refactor — Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Source:** Аудит документации (выполнен в разговоре)

<domain>
## Phase Boundary

Рефакторинг всей документационной поверхности проекта Adam-Chip по Концепции C + элемент A:
- **C (Lean Docs):** минимальная поверхность — только README, CLAUDE.md, RUNBOOK; CONTEXT.md удаляется
- **A (Config-First):** числовые параметры только в Config.json; добавляется Config.schema.json с описаниями

Фаза НЕ трогает: исходный код (кроме DEFAULT_CONFIG в config.py), ESP32-прошивку, скрипты, персону-файлы (Agent Adam Chip/).

</domain>

<decisions>
## Implementation Decisions

### D-01: Что делать с CONTEXT.md
Удалить CONTEXT.md. Его содержимое — снимок состояния системы, который мгновенно протухает. Всё, что нужно агенту для работы, уже есть в README.md (архитектура) + CLAUDE.md (инварианты) + Config.json (параметры). Вместо CONTEXT.md оставить ссылку-указатель: один абзац в README "полный снимок состояния: см. Config.json + CLAUDE.md".

### D-02: README.md — что остаётся, что уходит
Остаётся: архитектурная таблица (компоненты/роли), структура директорий, команды быстрого старта, команды диагностики, ссылки на документацию.
Уходит: таблица Inference Stack с конкретными параметрами (порты, модели, числа) — они теперь только в Config.json/schema. Ссылка "смотри Config.json" вместо повторения.

### D-03: CLAUDE.md — что остаётся
Остаётся: инварианты (LLM = чистый текст, power gate, half_duplex_mute, wake word), gotchas (Gemma thinking flag, SWA cache, curl proxy, Silero install order, audio devices, LLM model ID mismatch). Уходит: упоминания конкретных числовых значений (threshold=0.35, debounce=3) — это не инварианты, это конфиг.

### D-04: Config.schema.json — формат
JSON Schema Draft-07, файл `System/Config.schema.json`. Для каждого поля: `"description"` с объяснением (для кого это, что меняет), `"default"` с текущим актуальным значением, `"type"`, опционально `"enum"` для перечислений. Это НЕ валидатор — это документация в машиночитаемом формате. Файл не импортируется в код.

### D-05: DEFAULT_CONFIG в config.py — стратегия синхронизации
Обновить DEFAULT_CONFIG в `System/adam/config.py` чтобы он отражал текущие реальные значения из `System/Config.json`. DEFAULT_CONFIG — это фоллбэк при отсутствии Config.json, он должен давать рабочую систему. Список расхождений из аудита (10+ параметров).

### D-06: RUNBOOK — что исправить
Удалить блок "Current defaults" со строками 88-94 (Ollama-defaults, hw:0,0). Заменить ссылкой: "актуальные значения — System/Config.json". Оставить только процедуры (команды запуска, диагностики, переключения режимов).

### D-07: Исправление конкретных несоответствий
Точечно исправить в тех местах где данные дублируются намеренно (таблицы в README, CONTEXT):
- ASR model: "medium" → "small"
- wake_word.threshold: 0.35 → 0.20
- wake_word.debounce_hits: 3 → 2
Но в идеале — после D-01 (удаление CONTEXT.md) и D-02 (упрощение README) этих упоминаний вообще не останется.

### Claude's Discretion
- Порядок внутри Config.schema.json (группировать по секциям как в Config.json)
- Формулировки описаний в schema (на русском или английском — предпочтительно английский для единообразия с кодом)
- Нужно ли сохранить CONTEXT.md как архивный файл (CONTEXT.md.archive) или удалить полностью

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Конфигурация (источник истины)
- `System/Config.json` — актуальные значения ВСЕХ параметров системы
- `System/adam/config.py` — DEFAULT_CONFIG (устарел, нужна синхронизация), логика загрузки конфига

### Документация (объекты изменения)
- `CLAUDE.md` — инварианты и gotchas для Claude агента
- `README.md` — основной README проекта
- `CONTEXT.md` — файл-кандидат на удаление (снимок состояния)
- `docs/RUNBOOK_JETSON_EXHIBITION.md` — production runbook

### Персона (НЕ трогать)
- `Agent Adam Chip/` — все файлы персоны остаются без изменений

</canonical_refs>

<specifics>
## Specific Findings from Audit

### Критические несоответствия (требуют исправления):

| Параметр | В документах | В Config.json | Файлы |
|---|---|---|---|
| ASR model | `medium` | `small` | CONTEXT.md:46, README.md:40 |
| wake_word.threshold | `0.35` | `0.20` | CONTEXT.md:55 |
| wake_word.debounce_hits | `3` | `2` | CONTEXT.md:55 |
| LLM provider в RUNBOOK | `ollama / 11434` | `openai / 8081` | RUNBOOK:88-94 |
| audio input в RUNBOOK | `hw:0,0` | `pulse` | RUNBOOK:93 |

### DEFAULT_CONFIG расхождения (System/adam/config.py vs System/Config.json):

| Параметр | DEFAULT_CONFIG | Config.json |
|---|---|---|
| media.video.primary | `jetson_gstreamer` | `esp_mjpeg` |
| services.llm.max_tokens | `220` | `40` |
| services.asr.model | `medium` | `small` |
| services.asr.reply_window_sec | `6.0` | `3.75` |
| services.asr.reply_absolute_deadline_sec | `12.0` | `7.5` |
| services.tts.sample_rate | `48000` | `24000` |
| wake_word.threshold | `0.5` | `0.20` |
| wake_word.debounce_hits | `5` | `2` |

### Что хорошо задокументировано (не трогать):
- Порты сервисов (8080-8084, 8095) — везде согласованы
- ESP32 IP (192.168.0.171) — везде согласован
- audio input `pulse`, output `plughw:1,3` — согласованы
- half_duplex_mute, motor constraints, VAD aggressiveness — ОК

</specifics>

<deferred>
## Deferred

- Автогенерация документации из Config.schema.json (скрипт) — слишком сложно для этой фазы
- Обновление Agent Adam Chip/Engineering/ файлов — отдельная задача
- Обновление scripts/ файлов — вне скопа

</deferred>

---

*Phase: 01-doc-refactor-c-a*
*Context gathered: 2026-05-15*

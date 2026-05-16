---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Phase 7 ✓ COMPLETE (V-S07.3 mic stream stable). Phase 8 открыт — Reply-Echo-Hang debug.
last_updated: "2026-05-17T00:30:00.000Z"
progress:
  total_phases: 8
  completed_phases: 1
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Adam-Chip — Project State

**Last Updated:** 2026-05-17
**Status:** Phase 7 ✓ COMPLETE — ESP32 mic stream stable (+108 ms boot, 0 errors per session). Phase 8 открыт для устранения reply-echo-hang (заморозка voice_loop после reply_window_expired absolute_deadline из-за акустического эха TTS через ESP32 mic).

## Active Phase

Phase 7: ESP32 Mic Pipeline Refactor — MicReader keep-alive (ветка `V-S07.3-ESP32_mic_fix`).

- ✓ Plan 07-01: Config keys (disable_local_fallback, esp_open_timeout_sec, esp_probe_after_fails, esp_retry_backoff_sec)
- ✓ Plan 07-02: MicReader class в `System/adam/mic_reader.py`
- ✓ Plan 07-03: Orchestrator integration (этот SUMMARY) — commit `0c358a8`
- Plan 07-04: WebUI pipelineReady gate (chat.js, wakeMeter.js) — pending

→ [ACTIVE.md](.planning/ACTIVE.md) — активные ветки

## Completed Phases

### Phase 6B: Memory Search, Logging & Quality ✓ COMPLETE (2026-05-15)

Что сделано:

- `memory_search.py`: BM25Index + FaissEpisodeIndex (Wave 1 TF-IDF, faiss-cpu optional)
- `memory_metrics.py`: JSONL-логгер событий памяти; интеграция в Orchestrator + consolidator
- `GET /api/memory/status`: diary chars, episodes, echoes pool, last consolidation, metrics_last_24h
- `tests/test_memory_pipeline.py`: 34 unit + E2E теста, все зелёные

### Phase 6A: Memory Foundation ✓ COMPLETE (2026-05-15)

Что сделано:

- consolidator.py: Ollama → llama.cpp OpenAI API + rule-based fallback
- trim_gate_logs(): атомарная обрезка echoes_used + chinese_used
- TF-IDF matcher в echoes_gate.py (чистый Python, переключение через tuning.matcher_type)
- note_turn() с автотематизацией по кластерам из Tuning.json
- quick_patch_diary() — немедленная консолидация при salience ≥ 0.75
- is_recurring() — обнаружение повторных посетителей
- Все хардкоды вынесены в Tuning.json (score_boost, tag_short_cutoff, default_entry_weight)

→ Commit Wave 6A: `f6b2c5a`

### Phase 5: Agent Protocol — поведение агента-разработчика ✓ COMPLETE (2026-05-15)

Что сделано:

- `docs/AGENT-PROTOCOL.md` создан: 4 секции (Режимы работы, Триггеры уточнения, Гэпы контекста, Протокол планирования)
- `CLAUDE.md`: `@docs/AGENT-PROTOCOL.md` добавлен как @-reference (автозагрузка в каждую сессию)

→ Подробности: [phases/05-agent-protocol/](phases/05-agent-protocol/)

### Phase 4: Context Automation — per-directory CLAUDE.md и git hooks ✓ COMPLETE (2026-05-15)

Что сделано:

- `Subsystem/AdamsServer/CLAUDE.md`: ESP32 context (PlatformIO, PrivateConfig, IP 192.168.0.171, порты 80/81)
- `System/adam/CLAUDE.md`: карта 23 модулей (22 adam/*.py + Orchestrator.py) + 4 правила доступа
- `Agent Adam Chip/CLAUDE.md`: порядок персоны System→Identity→Lore→Abilities, запреты на разметку
- `.githooks/post-checkout`: scaffold BRANCH.md при checkout не-main ветки (POSIX sh, exit 0)
- `.githooks/pre-commit`: warning при отсутствии BRANCH.md, никогда не блокирует (exit 0)
- `CLAUDE.md` Quick start: команда активации хуков (`git config core.hooksPath .githooks`)

→ Подробности: [phases/04-context-automation/](phases/04-context-automation/)

### Phase 3: Branch Coordination — контекст для мульти-агентной работы ✓ COMPLETE (2026-05-15)

Что сделано:

- `docs/BRANCH-template.md` создан (шаблон + конвенция, без поля Owner)
- `.planning/ACTIVE.md` создан (таблица веток верифицирована через `git branch -a`)
- CLAUDE.md обновлён: инструкция читать BRANCH.md при работе на не-main ветке
- STATE.md получил ссылку на ACTIVE.md

→ Подробности: [phases/03-branch-coordination/](phases/03-branch-coordination/)

### Phase 2: Progressive Disclosure — навигация для нового агента ✓ COMPLETE (2026-05-15)

Что сделано:

- Reading Order добавлен в CLAUDE.md (Level 0–4 таблица с markdown-ссылками)
- README.md получил секцию "Текущее состояние" со ссылкой на STATE.md
- 01-SUMMARY.md создан для Phase 1 (Config-First, Lean Docs, навигация)
- Cross-link matrix 6/6 выполнена (ни один Level 0–4 файл не является тупиком)
- ROADMAP.md получил ссылку на REQUIREMENTS.md в шапке

→ Подробности: [phases/02-progressive-disclosure/](phases/02-progressive-disclosure/)

### Phase 1: Doc Refactor — Концепция C + A ✓ COMPLETE (2026-05-15)

Что сделано:

- Исправлены критические несоответствия: ASR model small, wake word threshold 0.20, debounce 2
- CONTEXT.md заменён минимальным указателем (lean docs)
- README.md упрощён: убраны числовые параметры из Inference Stack таблицы
- CLAUDE.md очищен от числовых параметров
- `System/Config.schema.json` создан — JSON Schema Draft-07 с 125 `description` + 108 `default` полями
- `System/adam/config.py` DEFAULT_CONFIG синхронизирован с Config.json
- RUNBOOK очищен от Ollama-defaults и неверного audio device

→ Подробности: [phases/01-doc-refactor-c-a/](phases/01-doc-refactor-c-a/)

## History

- 2026-05-16: Phase 7 Plan 03 завершён. Orchestrator интегрирует MicReader: lifespan управляет lifecycle; VoiceLoopController стал consumer'ом `get_chunk()` очереди; introduced `boot_warmup` voice_state; deleted `_run_esp32` / `_esp32_drain_during_mute` / `_audio_level_monitor` + per-turn drainer task; `_make_stereo_reader` promoted to module-level free function. Net -95 LOC. Commit `0c358a8`.
- 2026-05-16: Phase 7 Plan 02 завершён. MicReader class в `System/adam/mic_reader.py`. Commit `d67d6d4`.
- 2026-05-16: Phase 7 Plan 01 завершён. Config keys + schema docs. Commit `f5529b5`.
- 2026-05-15: Phase 6B завершена. memory_search.py, memory_metrics.py, /api/memory/status, 34 теста.
- 2026-05-15: Phase 6A завершена. llama.cpp в consolidator, rule-based fallback, TF-IDF, auto-themes, trim_gate_logs. Commit Wave 6A: f6b2c5a.
- 2026-05-15: Phase 5 завершена. AGENT-PROTOCOL.md, @-reference в CLAUDE.md. Все 5 фаз завершены.
- 2026-05-15: Phase 4 завершена. 3 per-directory CLAUDE.md, 2 git hooks, Quick start update.
- 2026-05-15: Phase 3 завершена. BRANCH-template.md, ACTIVE.md, BRANCH.md note в CLAUDE.md.
- 2026-05-15: Phase 2 завершена. Reading Order, Текущее состояние, 01-SUMMARY.md, cross-links.
- 2026-05-15: Phase 1 завершена. 3 атомарных коммита. Введена Config-First архитектура документации.
- 2026-05-15: Аудит документации выполнен. Найдены критические несоответствия: ASR model (medium vs small), wake word threshold (0.35 vs 0.20), debounce_hits (3 vs 2), RUNBOOK с Ollama-defaults.

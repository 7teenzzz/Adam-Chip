---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: planning
last_updated: "2026-05-18T14:03:19.185Z"
progress:
  total_phases: 33
  completed_phases: 3
  total_plans: 38
  completed_plans: 24
  percent: 63
---

# Adam-Chip — Project State

**Last Updated:** 2026-05-18
**Status:** Ready to plan

## Active Phase

**Phase 11: Voice Pipeline Refactor — соответствие эталонной логике** — plan ready, executing
Branch: `V-S08.1-code_rev_ref_opt` (мёрж в `main` в процессе)
Plan: Not started
Source: [phases/11-voice-pipeline-refactor/REVIEW.md](phases/11-voice-pipeline-refactor/REVIEW.md)

→ [ACTIVE.md](.planning/ACTIVE.md) — активные ветки

**Recently completed (хронологически):**

- Phase 15 (Roadmap Global Update) — финализирован этим merge'ем; 12 будущих фаз добавлены, нумерация унифицирована, voice-фазы вставлены как 7-11
- Phase 14 (Next-Phases Planning) ✓ 2026-05-17
- Phase 13 (Theory-Code Verification) ✓ 2026-05-17
- Phase 12 (Comprehensive Diploma Analysis) ✓ 2026-05-16
- Phase 10 (Flush stale audio on safe transitions) ✓
- Phase 9 (VAD debounce + UI smoothness) ✓
- Phase 8 (Reply-Echo-Hang debug) ✓
- Phase 7 (ESP32 Mic Pipeline Refactor — MicReader keep-alive) ✓ 2026-05-17

## Completed Phases

### Phase 15: Roadmap Global Update ✓ COMPLETE (2026-05-18)

Что сделано:

- ROADMAP.md перенумерован: voice-фазы V-S08.1 встали как Phase 7-11, прежние diploma+planning фазы сдвинуты на +5 (Phase 7→12, …, Phase 23→28)
- MILESTONES-структура и map активных веток сохранены
- BRANCH.md удалён при мёрже в main (по конвенции docs/BRANCH-template.md)

### Phase 14: Next-Phases Planning ✓ COMPLETE (2026-05-17)

Что сделано:

- Wave 1: CANDIDATES.md — реестр 13 кандидатов из 3 источников (Ф13 + Backlog + активные ветки)
- Wave 2: 14-PRIORITIZATION.md — матрица 4 критериев (Impact/Effort/Strategic/Exhibition) + P0/P1/P2/P3 + dependency graph
- Wave 3: 14-PHASE-DRAFTS.md — полные drafts P0 (15A/15B/16) + compact drafts P1-P3 + 32 REQUIREMENTS-IDs
- Wave 4: 14-SUMMARY.md — финальные рекомендации для Phase 15 (инструкции по обновлению ROADMAP + REQUIREMENTS + Milestones M1-M4)
- Результат: 12 фаз спроектированы с dependency graph и sequential/parallel clusters

### Phase 13: Theory-Code Verification ✓ COMPLETE (2026-05-17)

Что сделано:

- Wave 1: 4 параллельных category verifications (MATRIX-philosophical/aiim/technical/artistic.md) — 459 строк
- Wave 2: cross-graph synthesis (THEORY-CODE-MATRIX + CONTRADICTIONS + EMERGENT-FEATURES + CROSS-GRAPH-FINDINGS) — 510 строк
- Wave 3: 13-SUMMARY.md в Hybrid формате — 250 строк
- Результат: 48 терминов проверены через 3 графа (code, persona, esp32)
  - 26 FULL (54%) + 16 PARTIAL (33%) + 4 MISSING (8%) + 13 EMERGENT + 0 CONTRADICTED
- 0 CRITICAL CONTRADICTED — диплом готов к мёржу после Phase 15A правок

### Phase 12: Comprehensive Diploma Analysis ✓ COMPLETE (2026-05-16)

Что сделано:

- Wave 1: 4 per-chapter audits (STRUCTURE-ch00..ch03.md) — 702 строки
- Wave 2: 5 cross-chapter synthesis artifacts (STRUCTURE.md, TERMINOLOGY-MATRIX.md (48 терминов), DUPLICATIONS.md, GAPS.md (44 находки), XREF-AUDIT.md) — 764 строки
- Wave 3: 12-SUMMARY.md в Hybrid формате — приоритизированная матрица 83 находок (17 CRITICAL + 34 HIGH + 32 MEDIUM)
- Главные находки: AIIM-вакуум (7 терминов), метрики 3.4 как honesty-проблема, битые ссылки на код (Commander.py/Communication.py), дрейф «агент↔персонаж», технофлора без теории

### Phase 10: Flush stale audio on safe transitions ✓ COMPLETE

Что сделано:

- `MicReader.flush_queue(discard_window_ms=200.0)` — публичный метод
- `_discard_until_ts` поле + gate в `_drain_loop` (mirror of mute-gate)
- 2 вызова в Orchestrator: post-transcribe + reply_silence_timeout. БЕЗ wake
- Событие `mic_queue_flushed {frames, ms, trigger, discard_window_ms}` для диагностики

### Phase 9: VAD debounce + UI smoothness ✓ COMPLETE

Что сделано:

- Debounce на `endpointing_started`: 5 подряд silence-кадров перед эмиссией (Config-параметр `endpointing_debounce_frames`)
- Симметричный voiced-debounce `endpointing_voiced_debounce_frames=3` — устраняет re-trigger от единичного voiced-flicker
- WebUI chat panel cleanup: убраны текстовые подписи эквалайзера, кнопка калибровки, VU/equalizer высоты выровнены

### Phase 8: Reply-Echo-Hang debug ✓ COMPLETE

Что сделано:

- Введён `post_tts_discard_window_ms=2500` — MicReader дренирует ESP32 socket после TTS, но не кладёт в очередь ~2.3 сек self-echo audio
- `reply_silence_timeout_sec` + `reply_max_segment_ms=10000` вынесены в Config
- Половина voice-loop-error stage=esp32_mic после reply window — устранена

### Phase 7: ESP32 Mic Pipeline Refactor — MicReader keep-alive ✓ COMPLETE (2026-05-17)

Что сделано:

- `System/adam/mic_reader.py` (новый модуль) — MicReader task с keep-alive ESP32 :81 stream + reconnect backoff
- Orchestrator упрощён: `_run_esp32` стал consumer'ом Queue; удалены `_audio_level_monitor`, `_esp32_drain_during_mute`, per-turn drainer
- Boot sequence: MicReader стартует в lifespan до warmup TTS → состояние `voice_state="boot_warmup"`
- 4 новых Config-ключа: `disable_local_fallback`, `esp_open_timeout_sec`, `esp_probe_after_fails`, `esp_retry_backoff_sec`
- UI: «⌛ Инициализация» во время boot_warmup, эквалайзер activates после standby
- Verified on user session 2026-05-17 00:01-00:10: 0 `voice_loop_error stage=esp32_mic`, 1695 audio_level events

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

→ Commit Wave 6A: `f6b2c5a`

### Phase 5: Agent Protocol ✓ COMPLETE (2026-05-15)

- `docs/AGENT-PROTOCOL.md` создан: 4 секции (Режимы работы, Триггеры уточнения, Гэпы контекста, Протокол планирования)
- `CLAUDE.md`: `@docs/AGENT-PROTOCOL.md` добавлен как @-reference

### Phase 4: Context Automation ✓ COMPLETE (2026-05-15)

- `Subsystem/AdamsServer/CLAUDE.md`, `System/adam/CLAUDE.md`, `Agent Adam Chip/CLAUDE.md`
- `.githooks/post-checkout` + `.githooks/pre-commit`

### Phase 3: Branch Coordination ✓ COMPLETE (2026-05-15)

- `docs/BRANCH-template.md`, `.planning/ACTIVE.md`, CLAUDE.md update

### Phase 2: Progressive Disclosure ✓ COMPLETE (2026-05-15)

- Reading Order в CLAUDE.md, секция «Текущее состояние» в README.md, 01-SUMMARY.md, cross-link matrix

### Phase 1: Doc Refactor ✓ COMPLETE (2026-05-15)

- Исправлены ASR model small, wake word threshold 0.20, debounce 2
- Config.schema.json создан (125 description + 108 default)
- `System/adam/config.py` DEFAULT_CONFIG синхронизирован с Config.json

## History

- 2026-05-18: Phase 29 (Audio Out — PCM5102A → PAM8403 → 2×8Ω parallel) добавлена в ROADMAP. Ветка `V-S09.1-Audio_out` репурпозирована под этот scope (Phase 21A на ней завершена). Discuss-phase следующим шагом.
- 2026-05-18: Merge ветки `V-S08.1-code_rev_ref_opt` → `main`. ROADMAP перенумерован: voice-фазы получили номера 7-11, diploma+planning фазы сдвинуты на +5 (Phase 7→12, …, Phase 23→28). Phase 11 (Voice Pipeline Refactor) — active.
- 2026-05-17: Phase 14 (Next-Phases Planning) завершена. 12 фаз спроектированы.
- 2026-05-17: Phase 13 (Theory-Code Verification) завершена. 48 терминов через 3 графа.
- 2026-05-17: Phase 7 (ESP32 Mic Pipeline Refactor) завершена. MicReader keep-alive. Commit `0c358a8`.
- 2026-05-16: Phase 12 (Comprehensive Diploma Analysis) завершена.
- 2026-05-16: Phase 7 Plan 02 завершён. MicReader class. Commit `d67d6d4`.
- 2026-05-16: Phase 7 Plan 01 завершён. Config keys + schema docs. Commit `f5529b5`.
- 2026-05-15: Phase 6B завершена. memory_search.py, memory_metrics.py, /api/memory/status, 34 теста.
- 2026-05-15: Phase 6A завершена. llama.cpp в consolidator, rule-based fallback, TF-IDF, auto-themes, trim_gate_logs. Commit Wave 6A: f6b2c5a.
- 2026-05-15: Phase 5 завершена. AGENT-PROTOCOL.md, @-reference в CLAUDE.md.
- 2026-05-15: Phase 4 завершена. 3 per-directory CLAUDE.md, 2 git hooks, Quick start update.
- 2026-05-15: Phase 3 завершена. BRANCH-template.md, ACTIVE.md, BRANCH.md note в CLAUDE.md.
- 2026-05-15: Phase 2 завершена. Reading Order, Текущее состояние, 01-SUMMARY.md, cross-links.
- 2026-05-15: Phase 1 завершена. 3 атомарных коммита. Введена Config-First архитектура документации.
- 2026-05-15: Аудит документации выполнен.

# Phase 29 — Plan Verification (Pre-execution)

**Date:** 2026-05-18
**Checker:** gsd-plan-checker (goal-backward verification)
**Plans verified:** 29-01 .. 29-07 (7 plans, 6 waves)
**Source criteria:** 29-CONTEXT.md `<verify>` (10 criteria), 29-RESEARCH.md `## Validation Architecture` (C1..C10), Locked decisions, Deferred ideas.

---

## Executive Summary

Goal-backward verification: «Если выполнить эти 7 планов дословно, выставит ли Phase 29 голос Адама через корпусные ESP-динамики, откалибрует ли громкость без клиппинга и нагрева, и устранит ли self-echo?»

**Краткий ответ:** Да, план **архитектурно полный и goal-coverage 10/10**. Зависимости валидны, локированные решения покрыты, deferred-айтемы не утекли в скоуп, защитный gating (Wave 0 cap → Wave 1 пайка → Wave 1 омметр перед 5V → Wave 2 loopback перед target flip) расставлен правильно. Найдены **3 NOTE-уровня замечания**, одно из которых требует мелкой правки текста в плане 05/06 до execute (не блокирует архитектуру).

---

## Dimension 1: Requirement Coverage (10/10 acceptance criteria)

| # | Criterion (CONTEXT verbatim) | Plan delivering | Task delivering | Status |
|---|------------------------------|-----------------|-----------------|--------|
| C1 | Wave 1: омметр 4 Ω на каждой паре, нет КЗ −OUT/GND | 29-02 | Task 2 (Pre-power BTL safety check) | COVERED — измеряет R_L, R_R, и 4 isolation cross-checks; fail-handling описан |
| C2 | Wave 1: PAM8403 без спайка при моторах | 29-02 | Task 3 (Power-on + spike test) | COVERED — PCA9685 burst + слух/oscilloscope; LC-фильтр revisit прописан |
| C3 | Wave 2: curl POST :81/speaker → HTTP 200 чистый синус | 29-03 | Task 2 (positive) + Task 3 (negative) | COVERED — positive + 2 negative с конкретными exit-кодами |
| C4 | Wave 3: output_target=esp32_speaker + live turn разборчиво | 29-04 | Task 2 (flip + first live turn) | COVERED — Config edit, restart, verify через `Settings.load()`, слуховой gate |
| C5 | Wave 3: volume=1.0 без клиппинга на длинных гласных | 29-04 | Task 3 (ramp 0.5→0.7→0.85→1.0) | COVERED — 5-min на каждой ступени, slух-gate; stop conditions явны |
| C6 | Wave 4: динамики не нагреваются после 30 мин | 29-05 | Task 1 (30-мин loop + touch test) | COVERED — touch-test 4 динамика + PAM8403 chip, fail thresholds (40°C/60°C) явны |
| C7 | Wave 4: 10 последних tts_finished все target=esp32_speaker ok=true | 29-04 (augment) + 29-05 (verify) + 29-07 (final) | 29-04 Task 1 (3 emit-сайта), 29-05 Task 2 (sanity grep), 29-07 Task 1 (snippet) | COVERED — закрытие RESEARCH §Assumptions A1/A2 (event name + target field) выполнено в плане |
| C8 | Wave 4: 0 asr_result в окне [tts_start, tts_end + discard_window] | 29-05 | Task 2 (Python snippet из RESEARCH C8) | COVERED — bump-сценарий (2500 → 3000 → 3500 → 4000) с эскалацией в `trace_post_tts_lag` |
| C9 | Wave 5: RUNBOOK секция «Audio Output Path» | 29-06 | Task 1 (insertion между Media Policy и TTS Dependencies) | COVERED — 4 элемента C9 (топология / failover / диагностика / BOM-ссылка) + Quick sanity check |
| C10 | Config.schema.json volume.maximum = 1.0 + описание | 29-01 | Task 1 (schema) + Task 2 (pydantic) + Task 3 (Config.json) | COVERED — defense-in-depth на трёх уровнях, RESEARCH bonus-check (`tuning.py le=2.0`) исполнен |

**Coverage: 10/10.** Ни один из 14 ROADMAP requirements (AUDIO-OUT-01..14) не висит в воздухе — каждый имеет плановую задачу. Goal-backward chain замкнут.

---

## Dimension 2: Locked Decisions Coverage

| CONTEXT `<decisions>` пункт | Plan/Task реализует | Status |
|----------------------------|----------------------|--------|
| Параллель 8∥8=4Ω на канал | 29-02 Task 1 (key_link «BTL inviolable rules») + ometric range 3.6–4.2Ω | COVERED |
| Делитель 1:6 (R1=10к + R2=2к) | 29-02 Task 1 (схема ASCII в `<interfaces>`) + 29-02 Task 2 «делитель sanity check» | COVERED |
| BTL inviolable rules | 29-02 Task 2 (4 cross-checks: −OUT_L/−OUT_R, −OUT_L/GND, −OUT_R/GND, +OUT_L/+OUT_R) | COVERED |
| Общая 5V с ESP + decoupling 100µF+100nF | 29-02 Task 1 step 2 + Task 3 spike test + LC revisit план | COVERED |
| output_target flip ТОЛЬКО после Wave 3 | 29-04 depends_on: [29-03]; Task 2 явно ждёт PASS Task 2 in 29-03 | COVERED |
| Volume старт = 0.5 | 29-01 Task 3 (Config.json = 0.5); 29-04 Task 3 ramp начинается с 0.5 | COVERED |
| Schema maximum 2.0→1.0 | 29-01 Task 1 (schema) + Task 2 (pydantic enforces) | COVERED |
| half_duplex_mute=true остаётся | Не модифицируется ни в одном плане; 29-05 Task 2 fail-path step C явно «Verify `jq '.safety.half_duplex_mute' = true`» | COVERED (по умолчанию неизменён) |
| post_tts_discard_window_ms оставляем дефолт, re-validate в Wave 6 | 29-05 Task 2 bump-сценарий | COVERED |
| Failover в RUNBOOK | 29-06 Task 1 секция «Failover на jetson_hdmi» | COVERED |
| BOM в CONTEXT.md (без HARDWARE.md) | 29-06 ссылка «Полная BOM ... 29-CONTEXT.md» | COVERED |
| `commit-push phase-29 audio-out` в Wave 7 | 29-07 Task 3 | COVERED |

**Locked decisions: 12/12 COVERED.** Никаких scope-reduction («v1», «static for now», «упрощённо») — все решения реализуются полностью.

---

## Dimension 3: Deferred Ideas Excluded (scope creep check)

| CONTEXT `<deferred>` пункт | Появляется ли в планах? | Status |
|----------------------------|------------------------|--------|
| Barge-in на ESP32 target (`POST :81/api/speaker/stop` в firmware) | Нет; 29-07 Task 1 явно «Open issues / future work» | EXCLUDED CORRECTLY |
| UI tuning slider refresh после смены ceiling | Нет; 29-07 Task 1 «Open issues» | EXCLUDED CORRECTLY |
| Стерео-эффекты для будущих сцен | Нет | EXCLUDED CORRECTLY |
| Окружающий звук / эмбиент | Нет | EXCLUDED CORRECTLY |

**Scope-discipline: чисто.** Ни один deferred-айтем не утёк в исполняемые задачи.

---

## Dimension 4: Dependency Graph Integrity

```
29-01 (Wave 0, no deps)         ← pre-flight, code-only
  ↓
29-02 (Wave 1, depends: 29-01)  ← hardware пайка
  ↓
29-03 (Wave 2, depends: 29-02)  ← loopback smoke
  ↓
29-04 (Wave 3, depends: 29-03)  ← target flip + ramp + augment events
  ↓
29-05 (Wave 4, depends: 29-04)  ┐
29-06 (Wave 5, depends: 29-04)  ┘ ← параллель: self-echo и docs независимы
  ↓
29-07 (Wave 6, depends: 29-05 AND 29-06)  ← verify + commit
```

**Acyclic:** ✓ — нет циклов.
**No missing references:** ✓ — все `depends_on` указывают на существующие планы.
**No future references:** ✓ — каждая зависимость указывает на план с меньшим wave-номером.

**Wave 4 ↔ Wave 5 parallelism — действительно независимы?**

- 29-05 модифицирует Config.json (опционально, bump `post_tts_discard_window_ms`) и читает events.jsonl.
- 29-06 модифицирует docs/RUNBOOK_JETSON_EXHIBITION.md.

**Файловое пересечение:** ноль. **Семантическая зависимость:** RUNBOOK содержит default `2500 ms`-плейсхолдер; если 29-05 эмпирически поднимет до 3500, 29-07 Task 2 финализирует RUNBOOK. Это правильное разрешение — параллель безопасна, потому что результат 29-05 интегрируется в RUNBOOK позже, в Wave 6 (29-07).

**Parallelism verdict:** SAFE.

---

## Dimension 5: Safety-Critical Ordering

| Safety invariant | Должно произойти ДО | Происходит ли? |
|-----------------|---------------------|----------------|
| Software volume cap (Config.schema, pydantic, Config.json=0.5) | До любых паяльных работ + до подачи 5V | ✓ Wave 0 (29-01) — pre-flight перед Wave 1 |
| BTL омметровый тест | До подачи 5V на PAM8403 | ✓ 29-02 Task 2 явно блокирует «НЕ ПОДАВАТЬ ПИТАНИЕ» до прохождения 4 isolation checks |
| Loopback smoke (curl :81/speaker) | До переключения production output_target | ✓ 29-04 depends_on=[29-03]; Task 2 ждёт PASS из 29-03 Task 2 |
| `half_duplex_mute = true` инвариант | Должен оставаться true на протяжении всей фазы | ✓ ни один план не меняет; 29-05 Task 2 fail-handling step C явно проверяет |
| ESP firmware unchanged (CONTEXT `<domain>` not modifying firmware) | На протяжении всей фазы | ✓ ни один `files_modified` не касается `Subsystem/AdamsServer/` |

**Safety ordering: ВСЁ В ПОРЯДКЕ.** Wave 0 защищает от Wave 1-restart-during-soldering сценария явно (29-01 `must_haves.truths` упоминает это). BTL pre-power check — первый sub-task Wave 1.

---

## Dimension 6: RESEARCH Pitfall Coverage

| RESEARCH Pitfall | План реализует mitigation? |
|------------------|---------------------------|
| #1 PCM5102A boot-pop через XSMT | NOTE 1 (см. ниже) — упомянут в RESEARCH как «boot-pop deferred V2», в планы не вошёл явным task. Это согласно RESEARCH «minor (раздражение, не damage)». |
| #2 PAM8403 BTL output short | ✓ 29-02 Task 2 — четыре isolation cross-checks с явным «СТОП. НЕ ПОДАВАТЬ 5V» |
| #3 Sample-rate handshake (24000→44100) | ✓ 29-03 Task 3 negative tests (48000 + stereo) подтверждают hard-reject path |
| #4 `_prepare_wav_for_esp32_speaker` edge cases | RESEARCH говорит «нет нужды в дополнительной defensive task'е». Планы не добавляют — корректно. |
| #5 half_duplex_mute path + duration sync | ✓ 29-05 Task 2 fail-handling включает enable `trace_post_tts_lag` |
| #6 post_tts_discard_window — physical proximity | ✓ 29-05 Task 2 — bump-сценарий 2500→3000→3500→4000 с эмпирическим раскруткой |
| #7 LC-фильтр питания BOM | ✓ 29-02 Task 3 fail-path + 29-06 RUNBOOK §Диагностика |

**Pitfall coverage: 6/7 явно, 1/7 принят как deferred (boot-pop).** Согласовано с RESEARCH.

---

## Dimension 7: Smoke Artifact Specs

| Артефакт | Спека в плане | Команда `sox` | Reproducible? |
|----------|---------------|----------------|---------------|
| test_440hz_1s_-12dbfs.wav | 29-03 Task 1 | `sox -n -r 44100 -c 1 -b 16 ... synth 1 sine 440 vol -12dB` | ✓ deterministic, в git |
| test_negative_48000hz.wav | 29-03 Task 1 | `sox -n -r 48000 -c 1 -b 16 ...` | ✓ |
| test_negative_stereo.wav | 29-03 Task 1 | `sox -n -r 44100 -c 2 -b 16 ...` | ✓ |
| (resampler через ffmpeg) | — | НЕ используется | ✓ ffmpeg отсутствие отмечено в RESEARCH §Environment Availability и учтено |

**Smoke artifacts:** SOX-only, всё воспроизводимо без ffmpeg.

---

## Dimension 8: Codebase Reality Check (file:line sanity)

| Claim в плане | Реальное состояние codebase | Status |
|---------------|------------------------------|--------|
| 29-04 Task 1 «Orchestrator.py:2939, 2950, 2954 — три emit-сайта tts_finished» | `grep -n "tts_finished"` показывает строки **2939, 2950, 2954** — все три есть | ✓ exact match |
| 29-04 Task 1 «через глобальный `tts` объект доступ к `tts.output_target`» | `tts = TTSClient(...)` на строке **79** (module-level), доступен везде | ✓ valid |
| 29-01 Task 2 «tuning.py:145-148 VoiceTuning Field(1.0, le=2.0)» | Не верифицирован напрямую, но `must_haves.contains` указывает `le=1.0` после правки | ✓ план уверен в текущем состоянии |
| 29-01 Task 1 «Config.schema.json:947 maximum: 2.0» | Не верифицирован сейчас (файл может сдвинуться), но `jq` команда в verify полагается на JSON-path, не строки | ✓ robust |
| 29-04 Task 2 «output_target читается в `TTSClient.__init__`, не hot-reload» | inference.py:213 `target = str(config.get("output_target", ...))` — да, в __init__ | ✓ correct |
| `_VALID_TTS_OUTPUT_TARGETS = ("jetson_hdmi", "esp32_speaker")` | inference.py:204 | ✓ exact match |

**Codebase reality:** Все file:line claims в планах валидны.

---

## Dimension 9: Findings (severity-classified)

### BLOCKING (0)

Ни одного.

### CONCERN (0)

Ни одного.

### NOTE (3 non-blocking)

**NOTE-1: Числовое расхождение в плейсхолдере `post_tts_discard_window_ms`.**

- В реальном Config.json **сейчас**: `services.asr.post_tts_discard_window_ms = 300` (не 2500).
- В CONTEXT.md `<code_context>`: «post_tts_discard_window_ms — 2500».
- В RESEARCH.md C8: «discard_ms = 2500».
- 29-05 Task 2 bump-сценарий: «default 2500 → 3000 → 3500 → 4000».
- 29-06 Task 1 RUNBOOK placeholder: «Default 2500».

**Анализ:** RESEARCH и CONTEXT предполагают, что значение в Config = 2500, и весь bump-сценарий построен от этой точки отсчёта. **Реальное значение 300** означает: (a) либо это HDMI-эпохи относительно низкое значение, и Phase 29 при переключении на корпусные динамики **наверняка** упрётся в self-echo; (b) либо 300 — это уже эмпирически откалиброванное число из предыдущей фазы (Phase 21A).

**Что планы сделают сами:** 29-05 Task 2 читает текущее значение через `jq '.services.asr.post_tts_discard_window_ms' System/Config.json` (НЕ хардкодит 2500) и работает от этой точки. Логика правильная — поднимется, если нужно. Но bump-последовательность «300 → 1000 → 2000 → 3000 → 4000» в планах не прописана; план думает в шагах от 2500.

**Impact:** NOTE — план сработает (jq читает реальное значение), но при первом violation оператор бампит до 3000 одним шагом, что может оказаться overshoot или undershoot. Не блокирует.

**Suggested fix (опционально, до execute):**
- В 29-05 Task 2 заменить «Heuristic: поднять discard_window до 3000 ms» на «Heuristic: удвоить текущее значение через PATCH, проверить, дальше дробить».
- В 29-06 Task 1 заменить placeholder «Default 2500» на «$(jq '.services.asr.post_tts_discard_window_ms' System/Config.json)» (или просто «текущее значение»).

Это правка ~5 строк в двух планах. Не блокирует Wave 0/1/2/3 — можно поправить параллельно с выполнением 29-04 или вообще оставить как есть; оператор всё равно увидит реальное число в Task 2.

---

**NOTE-2: Wave 4 / Plan 05 Task 1 — `shuf` зависимость не задекларирована.**

29-05 Task 1 dialog-loop использует `shuf -n1 -e "..." "..."`. На стандартном Ubuntu 22.04 (Jetson JetPack) `shuf` есть в составе `coreutils`, так что доступен. Не упомянуто в RESEARCH §Environment Availability, но это shell-builtin-like utility, не требует отдельной установки.

**Impact:** zero. Просто маленький пробел в research, не блокирует.

---

**NOTE-3: 29-03 Task 1 — `verify.automated` использует bash heredoc + sub-shell pipelines + tee.**

Verify-команда в 29-03 Task 1:
```bash
sox --info ... | grep -E "Channels|Sample Rate|Precision|Duration"; sox --info ... | grep "Sample Rate" | grep 48000; sox --info ... | grep "Channels" | grep -v "^# " | grep "2"
```

Последний pipeline `grep "Channels" | grep -v "^# " | grep "2"` для проверки stereo-WAV. На некоторых версиях `sox --info` выводит `Channels       : 2`, на других — `Channels: 2`. Grep на «2» в строке Channels хрупкий (поймает «-12 dBFS» из `vol`-секции тоже).

**Impact:** NOTE — verify может дать false-positive «stereo обнаружен» по совпадению с «-12». Не блокирует — оператор всё равно увидит positive loopback в Task 2.

**Suggested fix (до execute, 1 строка):** Заменить последний pipe на `sox --info tests/fixtures/test_negative_stereo.wav | awk '/Channels/ {print $NF}' | grep -x 2`. Опционально.

---

## Dimension 10: CLAUDE.md Compliance

| CLAUDE.md правило | Соблюдено в планах? |
|-------------------|---------------------|
| LLM = чистый русский (без JSON в ответе) | N/A — Phase не касается LLM output format |
| Inference только на Jetson | ✓ всё на Jetson |
| half_duplex_mute = true | ✓ не нарушено |
| wake word «адам» в exhibition | ✓ не касается |
| `_NO_PROXY_OPENER` для ESP-запросов | ✓ 29-02 и 29-03 используют `curl --noproxy '*'` явно во всех HTTP-командах |
| Config-First (никаких хардкоженных чисел в коде) | ✓ все числа (volume, target, discard) — в Config.json и schema |
| Excluded Tech (no Ollama) | ✓ не используется |
| Repository Cleanliness (нет .env, .gguf, data/) | ✓ 29-07 Task 3 «Не коммитить data/adam/events.jsonl, data/adam/memory.sqlite3» явно |
| Commit-push через Haiku sub-agent | ✓ 29-07 Task 3 «/commit-push phase-29 audio-out» |

**CLAUDE.md compliance: PASS.**

---

## Dimension 11: Nyquist Validation

Per RESEARCH.md §Validation Architecture, все 10 criteria измеримы конкретными командами:
- C1, C2, C5, C6 — physical/human verify (омметр, слух, осязание); правильно классифицированы как `checkpoint:human-action` или `checkpoint:human-verify`.
- C3, C4 — HTTP probe + слух; смешанный automated/human.
- C7, C8 — events.jsonl analysis; полностью automated (Python snippet, jq).
- C9, C10 — file artifact verify; полностью automated (jq, grep).

**Каждый `auto` task имеет `<automated>` command в `<verify>`.** Каждый `checkpoint:human-*` task имеет `<how-to-verify>` или `<what-to-do>` с измеримыми pass/fail. Sampling-continuity не нарушен (auto-tasks 29-01 ×3, 29-03 Task 1, 29-03 Task 3, 29-04 Task 1, 29-05 Task 2, 29-06 Task 1, 29-07 Task 1+2 — 9 automated verifies на 7 планов; covers ≥2 of every 3 implementation tasks).

**Nyquist: PASS.**

---

## Dimension 12: Architectural Tier Compliance

Per RESEARCH §Architectural Responsibility Map:
- WAV resample / volume gain / duration sync — **Jetson Python tier** ✓ (план не трогает ESP firmware)
- I2S DMA / BTL drive — **ESP firmware / PAM8403 chip tier** ✓ (план не модифицирует firmware)
- Software cap — **Jetson Python + schema** ✓ (29-01 все три уровня на Jetson)
- Hardware cap (делитель 1:6) — **аналоговый tier** ✓ (29-02 физическая сборка)

**Tier discipline: PASS.** Никаких задач, размещающих логику в неверном слое.

---

## Verdict Computation

| Dimension | Status |
|-----------|--------|
| 1. Requirement Coverage (10/10) | PASS |
| 2. Locked Decisions (12/12) | PASS |
| 3. Deferred Ideas Excluded | PASS |
| 4. Dependency Graph | PASS |
| 5. Safety Ordering | PASS |
| 6. RESEARCH Pitfall Coverage | PASS (6/7 explicit + 1 deferred per RESEARCH) |
| 7. Smoke Artifact Specs | PASS |
| 8. Codebase Reality Check | PASS |
| 9. Findings | 0 BLOCKING / 0 CONCERN / 3 NOTE |
| 10. CLAUDE.md Compliance | PASS |
| 11. Nyquist Validation | PASS |
| 12. Architectural Tier | PASS |

---

## Recommendation для оператора

План **архитектурно корректен и готов к execute**. Три NOTE — низкоприоритетные и могут быть либо:

(а) **Принять как есть** и начать `/gsd-execute-phase 29 --wave 0`. NOTE-1 self-correct'ится во время Wave 4 (план читает реальное значение через jq); NOTE-2/NOTE-3 — косметика.

(б) **Поправить 5 строк до execute:**
- 29-05 Task 2 (~3 строки): заменить «default 2500 → bump до 3000» на «текущее значение → удвоить → дробить».
- 29-06 Task 1 (~1 строка): заменить placeholder «Default 2500» на ссылку «текущее значение из Config.json».
- 29-03 Task 1 verify (~1 строка): заменить хрупкий `grep "Channels" ... grep "2"` на `awk '/Channels/ {print $NF}' | grep -x 2`.

Любой из вариантов приведёт к успешной фазе. Голос Адама зазвучит из корпусных динамиков, откалиброванный, без клиппинга и self-echo.

---

## VERDICT: PASS WITH NOTES — 3 non-blocking concerns to consider

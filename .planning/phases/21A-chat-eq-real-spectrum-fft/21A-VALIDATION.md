---
phase: 21A
slug: chat-eq-real-spectrum-fft
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-18
---

# Phase 21A — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source of truth: `21A-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing `tests/` directory) |
| **Config file** | none — pytest auto-discovers `tests/test_*.py` |
| **Quick run command** | `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q` |
| **Full suite command** | `./.venv/bin/python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 sec quick / ~30–60 sec full |

---

## Sampling Rate

- **After every task commit:** `./.venv/bin/python -m pytest tests/test_mic_reader_spectrum.py -x -q`
- **After every plan wave:** `./.venv/bin/python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite green + browser smoke-test (see Manual-Only below)
- **Max feedback latency:** ~5 sec per task commit

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (assigned by planner) | 01 | 0 | UI-EQ-01 / 02 / 06 | — | N/A | Wave 0 stubs | n/a (creates test file) | ❌ W0 | ⬜ pending |
| (assigned) | 01 | 1 | UI-EQ-06 | — | N/A | unit | `pytest tests/test_mic_reader_spectrum.py::test_spectrum_keys_in_schema -x` | ❌ W0 | ⬜ pending |
| (assigned) | 02 | 1 | UI-EQ-01 | — | N/A | unit | `pytest tests/test_mic_reader_spectrum.py::test_sine_localised -x` | ❌ W0 | ⬜ pending |
| (assigned) | 02 | 1 | UI-EQ-01 | — | N/A | unit | `pytest tests/test_mic_reader_spectrum.py::test_silence_floor -x` | ❌ W0 | ⬜ pending |
| (assigned) | 02 | 1 | UI-EQ-01 | — | N/A | unit | `pytest tests/test_mic_reader_spectrum.py::test_noise_distributed -x` | ❌ W0 | ⬜ pending |
| (assigned) | 02 | 1 | UI-EQ-02 | — | N/A | unit | `pytest tests/test_mic_reader_spectrum.py::test_payload_shape -x` | ❌ W0 | ⬜ pending |
| (assigned) | 02 | 1 | UI-EQ-02 | — | N/A | unit | `pytest tests/test_mic_reader_spectrum.py::test_cadence_constant -x` | ❌ W0 | ⬜ pending |
| (assigned) | 02 | 2 | UI-EQ-06 | — | N/A | integration | `pytest tests/test_mic_reader_spectrum.py::test_hot_reload -x` | ❌ W0 | ⬜ pending |
| (assigned) | 03 | 2 | UI-EQ-03 | — | N/A | manual | Browser smoke-test §M-1 below | n/a | ⬜ pending |
| (assigned) | 03 | 2 | UI-EQ-04 | — | N/A | manual | Browser smoke-test §M-2 below | n/a | ⬜ pending |
| (assigned) | 03 | 2 | UI-EQ-05 | — | N/A | manual | Browser DevTools §M-3 below | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Plan IDs and exact Task IDs are assigned by the planner. Wave 0 must complete before Wave 1.

---

## Wave 0 Requirements

- [ ] `tests/test_mic_reader_spectrum.py` — stubs for all UI-EQ-01/02/06 unit and integration tests above
- [ ] `tests/conftest.py` — confirm presence; add fixture for synthetic mono-chunk generation (sine, silence, white noise at 16 kHz, 320 samples per chunk) if not already present
- [ ] Pytest framework already installed via `./.venv/bin/python -m pytest --version` — verified by existing `tests/` (no install needed)

---

## Manual-Only Verifications

| ID | Behavior | Requirement | Why Manual | Test Instructions |
|----|----------|-------------|------------|-------------------|
| M-1 | Bars track voice formants with no smoothing (instantaneous response) | UI-EQ-03 | Visual perception; no programmatic equivalent | Запустить оркестратор; открыть `http://JETSON:8080`, перейти на вкладку «Чат». Сказать «адам, проверка» в микрофон ESP32. Бары должны следовать за речью без заметной инерции; на тишине лежать плоско. |
| M-2 | Color gradient: green at low level, yellow at ~0.7, red at ~0.95 | UI-EQ-04 | Visual perception | Громко (≈1 м от mic) сказать длинную «а-а-а-а». Наблюдать переход цвета верхушки баров через жёлтый к красному при пике. На разговорной громкости — преимущественно зелёный. |
| M-3 | Single EventSource per page load even after 5× toggling between Chat and Settings panels | UI-EQ-05 | DevTools-driven check, no programmatic API | Открыть DevTools → Network → фильтр `eventsource`. Переключиться Chat → Settings → Chat 5 раз. Счётчик активных `eventsource`-соединений должен оставаться постоянным (1 на каждой страничке с виджетом, без накопления). |
| M-4 | Stale/synthetic `audio_level` (без `bands`) не ломает виджет — бары держат последний кадр, не падают и не зависают на нулях | UI-EQ-02 / UI-EQ-03 | Race condition, hard to simulate cleanly | Открыть Chat, дождаться нормальной работы. Через `iptables`/`tc` или ручное закрытие ESP32-потока симулировать stall. `_level_emit_loop` начнёт синтезировать backfill-events без `bands`. Бары должны "замёрзнуть" на последнем кадре, не упасть до нуля и не выдать `NaN`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test_mic_reader_spectrum.py)
- [ ] No watch-mode flags (-x stop on first failure used everywhere)
- [ ] Feedback latency < 10s (Wave 0 test file is small and isolated)
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 lands

**Approval:** pending

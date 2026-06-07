# Phase 6A: Memory Foundation — Context

**Status:** ✓ COMPLETE (2026-05-15)
**Branch:** `Memory-upgrade`
**Commit:** Wave 6A → `f6b2c5a`

> Ретроспективный CONTEXT.md. Фаза выполнена без GSD-артефактов (branch-driven).
> Восстановлен 2026-05-16 для целостности истории.

---

## Goal

Устранить критические проблемы пайплайна памяти без новых зависимостей.
Всё на чистом Python — никаких новых pip-пакетов в production path.

---

## Deliverables (A1–A8)

| ID | Файл | Что сделано |
|----|------|-------------|
| A1 | `Engineering/consolidator.py` | `call_ollama()` → `call_llm()` (llama.cpp OpenAI-compat API) |
| A2 | `Engineering/consolidator.py` | Rule-based fallback консолидации при недоступном LLM |
| A3 | `System/adam/memory.py` | `EpisodicMemory.trim_gate_logs()` — обрезка echoes_used + chinese_used JSONL |
| A4 | `System/adam/echoes_gate.py` + `Agent Adam Chip/Tuning.json` | Вынос хардкодов: `score_boost`, `tag_short_cutoff`, `default_entry_weight` |
| A5 | `System/adam/episodic.py` | `SessionAccumulator.note_turn()` — автотематизация по кластерам из Tuning.json |
| A6 | `System/adam/echoes_gate.py` | `TfIdfMatcher` — TF-IDF поиск эхо-фрагментов, переключение через `matcher_type` |
| A7 | `System/adam/memory.py` | `EpisodicMemory.quick_patch_diary()` — немедленная консолидация при salience ≥ threshold |
| A8 | `System/adam/memory.py` | `EpisodicMemory.is_recurring()` — обнаружение повторных посетителей |

---

## Key Decisions

- **Ollama запрещён** — заменён на llama.cpp через OpenAI-compat API (порт 8081). Причина: Ollama исключён из проекта, llama.cpp уже запущен для LLM.
- **TF-IDF без scikit-learn** — реализован на чистом Python, чтобы не добавлять зависимость конфликтующую с Jetson PyTorch.
- **Tuning.json как конфиг памяти** — параметры хранятся в hot-reload файле, не в Config.json, т.к. требуют частой подстройки под выставочный контекст.

---

## Files Modified

- `Engineering/consolidator.py`
- `System/adam/memory.py`
- `System/adam/episodic.py`
- `System/adam/echoes_gate.py`
- `Agent Adam Chip/Tuning.json`

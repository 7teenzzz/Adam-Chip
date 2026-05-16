# Phase 6B: Memory Search, Logging & Quality — Context

**Status:** ✓ COMPLETE (2026-05-15)
**Branch:** `Memory-upgrade`
**Depends on:** Phase 6A

> Ретроспективный CONTEXT.md. Фаза выполнена без GSD-артефактов (branch-driven).
> Восстановлен 2026-05-16 для целостности истории.

---

## Goal

Векторный поиск по эпизодам памяти (BM25 + FAISS CPU, Wave 1), метрики памяти,
REST API статуса, полное тестовое покрытие.

---

## Deliverables (B1–B6)

| ID | Файл | Что сделано |
|----|------|-------------|
| B1 | `System/adam/memory_search.py` | `BM25Index` — BM25 Okapi поиск (чистый Python) |
| B2 | `System/adam/memory_search.py` | `FaissEpisodeIndex` — FAISS CPU + TF-IDF векторы; graceful fallback без faiss-cpu |
| B3 | `System/adam/memory_metrics.py` | `MemoryMetrics` JSONL-логгер; интеграция в Orchestrator.py + consolidator.py |
| B4 | `System/adam/api_runtime.py` | `GET /api/memory/status` — diary_chars, episodes, echoes pool, last_consolidation, metrics_last_24h |
| B5 | `tests/test_memory_pipeline.py` | 34 теста (unit + E2E), все зелёные |
| B6 | `.planning/ROADMAP.md` + `.planning/STATE.md` | Обновлены по завершении |

---

## Key Decisions

- **Wave 1 = CPU-only** — FAISS cpu + TF-IDF векторы. Wave 2 (Neural, llama.cpp /embeddings) в Backlog до освобождения VRAM (условие: ≥ 4 GB свободно при работающем Gemma 4 E4B).
- **faiss-cpu опциональный** — graceful fallback на BM25 если faiss-cpu не установлен (несовместим с некоторыми Jetson окружениями).
- **JSONL-метрики** — формат совместим с существующим `data/adam/events.jsonl`, единый стек логгирования.

---

## Wave 2 (Backlog)

Neural search: заменить TF-IDF в `FaissEpisodeIndex` на llama.cpp `/embeddings`.
Интерфейс не меняется (`.build()` / `.search()` / `.save()` / `.load()`).
Условие запуска: VRAM ≥ 4 GB свободно.

---

## Files Created / Modified

- `System/adam/memory_search.py` (новый)
- `System/adam/memory_metrics.py` (новый)
- `System/adam/api_runtime.py` (добавлен эндпоинт)
- `System/Orchestrator.py` (интеграция MemoryMetrics)
- `Engineering/consolidator.py` (интеграция MemoryMetrics)
- `tests/test_memory_pipeline.py` (новый)

# BRANCH: MemoryFixes

**Цель:** Phase 30 — заставить пулы Echoes (`About/Echoes.md`) и Chinese
(`About/Chinese_lines.md`) реально инжектиться в диалог. Устранить корневую
причину: gate матчит теги-образы карточек против сырого транскрипта зрителя →
пересечение словарей почти нулевое.

**Базовая ветка:** `main`.

**Фаза:** [.planning/phases/30-echoes-chinese-gate-activation/](.planning/phases/30-echoes-chinese-gate-activation/)
Контекст: [30-CONTEXT.md](.planning/phases/30-echoes-chinese-gate-activation/30-CONTEXT.md)

## Scope (4 слоя)

- **A** — тематический мост (`acc.themes` ∪ ключи кластеров) + окно истории
  (зритель + Адам) вместо матча против сырой реплики
- **B** — мягкий вероятностный движок (`thematic × weight × recency`) вместо
  жёсткого порога 0.55
- **C** — спонтанный канал инжекта по внутренним сигналам (пауза/глубина сессии)
- **D** — анти-повтор кластера за сессию + починка мёртвого `mood`/`mood_block`
- **Chinese** — `enabled=true` + ослабление порога + `ru_hint` для LLM

## Затрагиваемые файлы (план)

- `System/adam/echoes_gate.py` — матчинг, скоринг, выбор, анти-повтор, спонтанный канал
- `System/Orchestrator.py` — прокидка окна истории + тем в gate, починка mood
- `System/Config.json` + `System/Config.schema.json` — новые параметры (Config-First)
- `tests/` — тесты gate

## Вне scope (deferred)

- Pre-rendered wav-озвучка китайских фраз (`audio_id`) — отдельная фаза
- Полноценный LLM-driven mood — Phase 19
- Нейросетевые эмбеддинги — Phase 20

## Условия мёржа в main

- Echoes реально инжектятся на тематически близких репликах (тест проходит)
- Chinese-пул активен, `ru_hint` уходит в `[hint]`
- Все новые числа в Config.json + schema
- `/gsd-code-review` пройден
- Регрессия диалогового pipeline (тон/поведение Адама не сломаны)

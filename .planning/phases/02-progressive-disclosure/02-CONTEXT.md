---
phase: 2
title: Progressive Disclosure — навигация для нового агента
status: planning
date: 2026-05-15
---

# Phase 2 Context: Progressive Disclosure

## Problem Statement

После Phase 1 система документации имеет правильный контент, но не является прогрессивно раскрывающейся. Новый агент/аккаунт не имеет чёткого entry point и вынужден либо читать все файлы, либо угадывать порядок.

**Конкретные пробелы (из анализа):**

1. `CLAUDE.md` — нет секции "с чего начать"; нет ссылок на STATE.md / ROADMAP.md
2. `README.md` — нет ссылки на текущее состояние проекта
3. `STATE.md` — существует, но ни один файл верхнего уровня на него не ссылается
4. `ROADMAP.md` — Phase 1 не помечена как завершённая (все планы `[ ]`)
5. `.planning/phases/01-doc-refactor-c-a/` — нет SUMMARY.md с итогом что было сделано
6. Перекрёстные ссылки между уровнями отсутствуют

## Target Architecture (Level 0–4)

```
Level 0 — Entry point:      CLAUDE.md          ← агент читает первым
Level 1 — Project overview: README.md          ← архитектура + быстрый старт
Level 2 — Current status:   .planning/STATE.md ← что сейчас активно
Level 3 — History/plan:     .planning/ROADMAP.md + REQUIREMENTS.md
Level 4 — Phase detail:     .planning/phases/NN-*/NN-SUMMARY.md + PLAN.md
```

## Decisions

- **CLAUDE.md получает секцию "Reading Order"** в самом начале файла — 5 строк с иерархией и ссылками.
- **README.md получает секцию "Текущее состояние"** (1–2 строки + ссылка на STATE.md) сразу после описания архитектуры.
- **STATE.md** обновляется: Phase 1 → ✓ COMPLETE, Phase 2 → Planning (уже сделано в этой сессии).
- **ROADMAP.md** обновляется: Phase 1 plans → [x], Completed date добавлена (уже сделано в этой сессии).
- **01-SUMMARY.md** создаётся в phases/01-doc-refactor-c-a/ — одна страница с принятыми решениями и принципами (Config-First, Lean Docs).
- **ToDo.md** получает указатель на ROADMAP.md (уже сделано), ROADMAP.md получает секцию Backlog с задачами из ToDo.md (уже сделано).

## Constraints

- Не добавлять параметры/числа в markdown файлы — правило Config-First.
- Минимальная поверхность — не создавать новые файлы без необходимости.
- CLAUDE.md — русский язык общения; комментарии в коде — английский.

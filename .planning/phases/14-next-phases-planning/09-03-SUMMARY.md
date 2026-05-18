---
phase: 09-next-phases-planning
plan: 03
subsystem: planning
tags:
  - planning
  - phase-drafts
  - roadmap
  - requirements
dependency_graph:
  requires:
    - 09-02 (PRIORITIZATION matrix — P0/P1/P2/P3 groups)
    - 08-SUMMARY.md (phase candidates §4.1)
    - CANDIDATES.md (raw phase data)
    - EMERGENT-FEATURES.md (13 фич)
    - CONTRADICTIONS.md (path A/B/C рекомендации)
  provides:
    - 09-PHASE-DRAFTS.md (copy-paste-ready for Phase 10)
  affects:
    - Phase 10 (Roadmap Global Update) — потребляет PHASE-DRAFTS напрямую
    - REQUIREMENTS.md — готовы к добавлению в Phase 10
tech_stack:
  added: []
  patterns:
    - Hybrid documentation format (full ROADMAP-style + compact)
    - REQ prefix conventions per phase
key_files:
  created:
    - .planning/phases/09-next-phases-planning/09-PHASE-DRAFTS.md
  modified: []
decisions:
  - "REQ prefix conventions: DIPL- (10A), CFG- (10B), AIIM- (11), MEM- (13), MOOD- (14), MEMN- (15), UI- (16), REM- (17), REF- (18), PROAC- (19), VLM- (20), ID- (21)"
  - "Phase 13 branch: memory-consolidation (new, separate from Memory-upgrade) — изоляция рисков"
  - "Phase 10A Delivers: совмещения из Ф8 §4.3 применены (EMERGENT #3+#8+Α-24 = одна правка; #7+Τ-36 = одна задача)"
metrics:
  duration: "~25 min"
  completed: "2026-05-17T10:24:55Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
---

# Phase 09 Plan 03: Phase Drafts Summary

**One-liner:** Написан 09-PHASE-DRAFTS.md — гибридный документ с полными ROADMAP-style drafts для 3 P0-фаз (10A/10B/11), компактными записями для 9 P1-P3 фаз, и предложением 32 новых REQUIREMENTS-IDs по 12 префиксам.

---

## What was done

Создан `09-PHASE-DRAFTS.md` (450 строк) — главный deliverable Phase 9.

### §1 — Full ROADMAP-style drafts (P0)

**Phase 10A: Diploma Convergence Pass** — полный draft с 7 Delivers (правки ch01.1.1.4, ch03.3.2.2/3/6, ch03.3.3.4, ch03.3.4, ch03.3.1.2 + C-path ремарки). Применяет EMERGENT #1–#10, #12, #13 (10 оставшихся после топ-3). Requirements: DIPL-09..DIPL-15.

**Phase 10B: Config-First Refactor** — full draft с 9 Delivers (4 новых Config-ключа, рефакторинг prompt.py/episodic.py/consolidator.py, unit-тесты). Requirements: CFG-01..CFG-04.

**Phase 11: AIIM Dynamic** — full draft с 7 Delivers (aiim_reflection.py, whitelist/magnitude_limits в Config, API endpoint, регрессионный тест). Requirements: AIIM-01..AIIM-04.

### §2 — Compact drafts (P1–P3)

9 компактных блоков: Phase 13 (MEM-), Phase 21 (ID-), Phase 14 (MOOD-), Phase 15 (MEMN-), Phase 17 (REM-), Phase 20 (VLM-), Phase 19 (PROAC-), Phase 16 (UI-), Phase 18 (REF-).

### §3 — REQUIREMENTS proposal

32 новых REQUIREMENTS-IDs по 12 REQ-префиксам — готовы к вставке в `REQUIREMENTS.md` в Phase 10.

### §4 — Logical groups + dependency chains

Три логические группы, dependency graph (текст + Mermaid), sequential и parallel clusters.

---

## Decisions Made

1. **REQ prefix conventions** зафиксированы строго по таблице из PLAN.md — не изменялись.

2. **Phase 13 ветка** = `memory-consolidation` (новая, отдельная от `Memory-upgrade`) — изоляция рисков консолидации от Neural search (Wave 2).

3. **Phase 10A Delivers** применяет совмещения из Ф8 §4.3: EMERGENT #3+#8+Α-24 = одна редактура ch03.3.2.6; EMERGENT #7+Τ-36 = одна задача; EMERGENT #6+Χ-46 = одна правка ch03.3.2.2. Это уменьшает количество коммитов при максимальном охвате.

4. **Mode = standard** для всех фаз — нет явных оснований для mvp/discovery.

5. **DIPL-13 vs Phase 10B** — diploma-side правка formulas salience отнесена к Phase 10A (DIPL-13), Phase 10B отвечает только за code-side (CFG-03). При параллельном выполнении — избыточности нет.

---

## Deviations from Plan

None — план выполнен точно как написан. Все 9 компактных drafts присутствуют. Все REQ-префиксы из таблицы `<interfaces>` использованы. Файл превышает min_lines=250 (450 строк).

---

## Self-Check

- [x] `09-PHASE-DRAFTS.md` создан: `f:\Adam-Chip\.planning\phases\09-next-phases-planning\09-PHASE-DRAFTS.md`
- [x] Содержит `## Phase 10A:`, `## Phase 10B:`, `## Phase 11:` (full ROADMAP-style)
- [x] Содержит 9 компактных drafts (`### Phase 13:` .. `### Phase 18:`)
- [x] REQ-префиксы DIPL-, CFG-, AIIM-, MEM-, MOOD-, MEMN-, UI-, REM-, REF-, PROAC-, VLM-, ID- присутствуют
- [x] Section §4 «Logical groups» присутствует с Mermaid-диаграммой
- [x] Файл 450 строк (минимум 250)
- [x] Commit: `14630b1` — `docs(09-03): write phase drafts — full P0 + compact P1-P3 + REQUIREMENTS proposal`

## Self-Check: PASSED

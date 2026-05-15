# Adam-Chip — Project State

**Last Updated:** 2026-05-15
**Status:** All documentation phases complete

## Active Phase

Все документационные фазы (1–5) завершены. Система готова к выставочному использованию.
Следующие задачи: см. Backlog в [ROADMAP.md](.planning/ROADMAP.md).
→ [ACTIVE.md](.planning/ACTIVE.md) — активные ветки

## Completed Phases

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

- 2026-05-15: Phase 5 завершена. AGENT-PROTOCOL.md, @-reference в CLAUDE.md. Все 5 фаз завершены.
- 2026-05-15: Phase 4 завершена. 3 per-directory CLAUDE.md, 2 git hooks, Quick start update.
- 2026-05-15: Phase 3 завершена. BRANCH-template.md, ACTIVE.md, BRANCH.md note в CLAUDE.md.
- 2026-05-15: Phase 2 завершена. Reading Order, Текущее состояние, 01-SUMMARY.md, cross-links.
- 2026-05-15: Phase 1 завершена. 3 атомарных коммита. Введена Config-First архитектура документации.
- 2026-05-15: Аудит документации выполнен. Найдены критические несоответствия: ASR model (medium vs small), wake word threshold (0.35 vs 0.20), debounce_hits (3 vs 2), RUNBOOK с Ollama-defaults.

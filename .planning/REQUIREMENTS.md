# Requirements

## Phase 1 — Doc Refactor: Концепция C + A ✓ COMPLETE

Все выполнены. Итог: [phases/01-doc-refactor-c-a/](phases/01-doc-refactor-c-a/)

| ID | Requirement |
|----|-------------|
| DOC-01 | Исправить ASR model в CONTEXT.md и README.md: "medium" → "small" |
| DOC-02 | Исправить wake word threshold в CONTEXT.md: 0.35 → 0.20 |
| DOC-03 | Исправить wake word debounce_hits в CONTEXT.md: 3 → 2 |
| DOC-04 | Удалить/переписать устаревшие Ollama-defaults из docs/RUNBOOK_JETSON_EXHIBITION.md; исправить audio input device hw:0,0 → pulse |
| DOC-05 | Создать System/Config.schema.json с JSON Schema описаниями всех параметров Config.json |
| DOC-06 | Синхронизировать DEFAULT_CONFIG в System/adam/config.py с реальными значениями System/Config.json |
| DOC-07 | Удалить CONTEXT.md или свести к указателю; убрать числовые параметры из README.md и CLAUDE.md, которые дублируют Config.json |

## Phase 2 — Progressive Disclosure: навигация для нового агента

| ID | Requirement |
|----|-------------|
| NAV-01 | Обновить `.planning/STATE.md`: Phase 1 помечена ✓ COMPLETE с кратким итогом реализованных изменений |
| NAV-02 | Обновить `.planning/ROADMAP.md`: Phase 1 помечена ✓ done с датой завершения; Phase 2 добавлена |
| NAV-03 | Создать `.planning/phases/01-doc-refactor-c-a/01-SUMMARY.md` — одностраничный итог Phase 1: что изменено, принятые решения, принципы (Config-First, Lean Docs) |
| NAV-04 | Добавить секцию "Reading Order" в `CLAUDE.md`: иерархия файлов Level 0–4 с ссылками, указание с чего начать новому агенту |
| NAV-05 | Добавить секцию "Текущее состояние" в `README.md` с ссылкой на `.planning/STATE.md` и кратким статусом |
| NAV-06 | Проверить и добавить перекрёстные ссылки между Level 0–4 документами (CLAUDE.md ↔ README.md ↔ STATE.md ↔ ROADMAP.md ↔ phase SUMMARY) |

## Phase 3 — Branch Coordination: контекст для мульти-агентной работы

| ID | Requirement |
| --- | ----------- |
| BR-01 | Создать `docs/BRANCH-template.md` — шаблон BRANCH.md + конвенция (когда создавать, как заполнять, удалять после мёржа без архива; имя ветки = идентификатор, нет поля Owner) |
| BR-02 | Создать `.planning/ACTIVE.md` — таблица активных веток: ветка / статус / modified areas / merge blocker. Обновляется при создании и закрытии ветки, не в середине работы |
| BR-03 | Обновить `CLAUDE.md` Reading Order: добавить строку «если не на main — прочитай `BRANCH.md` первым» |
| BR-04 | Обновить `.planning/STATE.md`: добавить ссылку на `.planning/ACTIVE.md` в раздел Active Phase |

## Phase 4 — Context Automation: per-directory CLAUDE.md и git hooks

| ID | Requirement |
| --- | ----------- |
| CTX-01 | Создать `Subsystem/AdamsServer/CLAUDE.md` — ESP32 tech context: PlatformIO build system, запрещённые файлы (`PrivateConfig.h`, `credentials.h`), flash tools, static IP `192.168.0.171`, порты 80/81 |
| CTX-02 | Создать `System/adam/CLAUDE.md` — карта всех 23 модулей (одна строка на модуль), `Settings.load()` как единственный config entrypoint, service adapter pattern (только через `inference.py`), EventBus convention |
| CTX-03 | Создать `Agent Adam Chip/CLAUDE.md` — порядок загрузки персоны (System.md → Identity.md → Lore.md → Abilities.md), запрет на JSON/code blocks, зависимость порядка от `Config.json agent.persona_paths` |
| CTX-04 | Создать `.githooks/post-checkout` (POSIX sh) — scaffold BRANCH.md при переключении на новую не-main ветку если `docs/BRANCH-template.md` существует |
| CTX-05 | Создать `.githooks/pre-commit` (POSIX sh) — warning (не блок) если коммит на не-main ветке и BRANCH.md отсутствует |
| CTX-06 | Обновить root `CLAUDE.md` Quick start: добавить команду `git config core.hooksPath .githooks && chmod +x .githooks/*` |

## Phase 5 — Agent Protocol: поведение агента-разработчика

| ID | Requirement |
| --- | ----------- |
| AGT-01 | Создать `docs/AGENT-PROTOCOL.md` секция "Режимы работы": таблица Advisor / Planner / Implementer / Debugger с триггерами переключения |
| AGT-02 | Добавить в `docs/AGENT-PROTOCOL.md` секция "Триггеры уточнения": конкретный список условий (Config.json изменение, shared infrastructure, размытый глагол, >3 модулей, global vs experiment) |
| AGT-03 | Добавить в `docs/AGENT-PROTOCOL.md` секция "Гэпы контекста": классификация Branch gap / Phase gap / Config gap / Invariant gap / Stale gap + поведение агента для каждого |
| AGT-04 | Добавить в `docs/AGENT-PROTOCOL.md` секция "Протокол планирования": GSD-first (проверить ROADMAP.md → рекомендовать `/gsd-plan-phase` → inline GSD-формат для малых задач) |
| AGT-05 | Обновить `CLAUDE.md`: добавить `@docs/AGENT-PROTOCOL.md` в строку с `@`-референсами и однострочную подпись |

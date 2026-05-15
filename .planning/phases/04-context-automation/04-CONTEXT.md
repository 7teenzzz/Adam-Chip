---
phase: 4
title: Context Automation — per-directory CLAUDE.md и git hooks
status: planning
date: 2026-05-15
---

# Phase 4 Context: Context Automation

## Team

2 разработчика × 2 Claude-аккаунта = до 4 агентов одновременно. Каждый агент начинает сессию без памяти предыдущих.

## Problem Statement

Два класса проблем:

**1. Переключение директорий.** При работе в `Subsystem/AdamsServer/` (C++/PlatformIO) агент не знает что он в другом tech stack — нет явного сигнала. При работе в `System/adam/` агент не имеет карты 23 модулей. Claude Code автоматически загружает CLAUDE.md из любой директории — но их нет нигде кроме корня.

**2. Переключение веток.** При создании новой ветки агент или разработчик должны вручную создать BRANCH.md. Это конвенция без enforcement — забывается.

## Mechanism

**Per-directory CLAUDE.md** — стандартная фича Claude Code. Загружается автоматически при работе в директории + все родительские. Добавляем только там, где контекст принципиально отличается от родителя.

**Git hooks** — POSIX sh скрипты в `.githooks/`. Активируются через `git config core.hooksPath .githooks`. Работают на Windows (через Git's sh.exe) и Ubuntu одинаково.

## Decisions

**Три директории для per-directory CLAUDE.md:**

`Subsystem/AdamsServer/` — максимальный разрыв с root:
- Build: PlatformIO (pio), не Python/pip
- Запрещённые файлы: `config/PrivateConfig.h`, `config/credentials.h`
- Flash: `tools/flash_com7.ps1` (COM7 = прошивка, COM6 = логи)
- OTA: `tools/flash_ota.ps1`
- Static IP: `192.168.0.171` (W5500 Ethernet, не Wi-Fi)
- Порт 80 = HTTP API, порт 81 = отдельный сервер (speaker + camera stream)
- НЕ менять разделение портов 80/81 без синхронизации с Config.json

`System/adam/` — карта 23 модулей, паттерны доступа:
- Config: только `Settings.load()` или `settings.section("name")` — никогда DEFAULT_CONFIG напрямую
- Сервисы: только через `inference.py` — не вызывать LLM/TTS/ASR/VLM из других модулей
- События: `events.EventBus` — не `print()`/`logging.getLogger()`
- Hot-reload: `tuning.py` значения читать каждый turn, не кешировать в `__init__`
- Карта модулей: одна строка на каждый из 23 модулей

`Agent Adam Chip/` — порядок и роли файлов персоны:
- Загружаются в системный промпт в порядке из `Config.json agent.persona_paths`
- Порядок: System.md → Identity.md → Lore.md → Abilities.md
- Нельзя менять порядок без обновления `Config.json agent.persona_paths`
- Нельзя добавлять JSON, code blocks, markdown-таблицы — LLM получает plain text
- Заголовки (##) влияют на парсинг в `prompt.py` — проверять после изменений
- Язык файлов: только русский

**Два git хука (POSIX sh):**

`.githooks/post-checkout`:
- Триггер: переключение ветки (`$3 == 1`), destination не main, `BRANCH.md` не существует, `docs/BRANCH-template.md` существует
- Действие: `sed "s/{branch-name}/$BRANCH/g" docs/BRANCH-template.md > BRANCH.md`
- Вывод: `[hook] BRANCH.md scaffolded — fill in Goal and Merge conditions`

`.githooks/pre-commit`:
- Триггер: коммит на не-main ветке, `BRANCH.md` не найден
- Действие: warning message, не блокировать (`exit 0`)

**Установка:**
- Одна команда на обеих платформах: `git config core.hooksPath .githooks`
- На Linux: дополнительно `chmod +x .githooks/*`
- Добавить в CLAUDE.md Quick start

## Scope (что входит)

- CTX-01: `Subsystem/AdamsServer/CLAUDE.md`
- CTX-02: `System/adam/CLAUDE.md` с картой всех 23 модулей
- CTX-03: `Agent Adam Chip/CLAUDE.md`
- CTX-04: `.githooks/post-checkout`
- CTX-05: `.githooks/pre-commit`
- CTX-06: Обновить root `CLAUDE.md` Quick start — команда установки хуков

## Scope (что НЕ входит)

- CLAUDE.md в `docs/`, `scripts/`, `.planning/` — lean docs, не нужны
- Автоматическое обновление ACTIVE.md через хук — слишком хрупко
- commit-msg хук — отдельная задача
- Ретроактивное создание BRANCH.md для существующих веток

## Dependencies

**Requires:**
- Phase 2 завершена (Reading Order в CLAUDE.md для CTX-06 вставки)
- Phase 3 завершена (`docs/BRANCH-template.md` для post-checkout hook)

## Relation to Phase 5

Phase 5 (Agent Protocol) имеет триггер уточнения: «задача затрагивает inference.py, Orchestrator.py, prompt.py → shared infrastructure». После Phase 4 `System/adam/CLAUDE.md` будет содержать карту модулей — агент получит этот контекст автоматически. AGT-02 (Phase 5) дополняет, не дублирует Phase 4: Phase 4 описывает ЧТО модули делают, Phase 5 говорит КОГДА предупреждать.

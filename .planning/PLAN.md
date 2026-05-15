---
phase: doc-system-unified
plan: phases-2-5
type: execute
autonomous: true
requirements:
  - NAV-01, NAV-02, NAV-03, NAV-04, NAV-05, NAV-06
  - BR-01, BR-02, BR-03, BR-04
  - CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, CTX-06
  - AGT-01, AGT-02, AGT-03, AGT-04, AGT-05
files_modified:
  - .planning/STATE.md
  - .planning/ROADMAP.md
  - .planning/phases/01-doc-refactor-c-a/01-SUMMARY.md
  - CLAUDE.md
  - README.md
  - docs/BRANCH-template.md
  - .planning/ACTIVE.md
  - Subsystem/AdamsServer/CLAUDE.md
  - System/adam/CLAUDE.md
  - Agent Adam Chip/CLAUDE.md
  - .githooks/post-checkout
  - .githooks/pre-commit
  - docs/AGENT-PROTOCOL.md
---

<objective>
Выполнить Phases 2–5 документационной системы Adam-Chip последовательно через четыре волны.

Purpose: 4 агента (2 разработчика × 2 Claude-аккаунта) работают в одном репо. Новый агент должен прочитать CLAUDE.md → README.md → STATE.md и получить полное понимание проекта. Агент на не-main ветке должен сразу найти BRANCH.md. Агент в любой поддиректории получает специализированный контекст автоматически.

Output:
- Phase 2: Reading Order в CLAUDE.md, Текущее состояние в README.md, 01-SUMMARY.md для Phase 1
- Phase 3: docs/BRANCH-template.md, .planning/ACTIVE.md с верифицированными ветками, BRANCH.md note в CLAUDE.md
- Phase 4: 3 per-directory CLAUDE.md (ESP32, Python agents, persona) + 2 git hooks + Quick start update
- Phase 5: docs/AGENT-PROTOCOL.md с 4 секциями + @-reference в CLAUDE.md

Waves: каждая волна = одна фаза. Waves строго последовательны — каждая depends_on предыдущей.
</objective>

<execution_context>
@F:\Adam-Chip\.planning\phases\02-progressive-disclosure\02-CONTEXT.md
@F:\Adam-Chip\.planning\phases\03-branch-coordination\03-CONTEXT.md
@F:\Adam-Chip\.planning\phases\04-context-automation\04-CONTEXT.md
@F:\Adam-Chip\.planning\phases\05-agent-protocol\05-CONTEXT.md
</execution_context>

<context>
@F:\Adam-Chip\.planning\STATE.md
@F:\Adam-Chip\.planning\ROADMAP.md
@F:\Adam-Chip\.planning\REQUIREMENTS.md
@F:\Adam-Chip\CLAUDE.md
@F:\Adam-Chip\README.md
@F:\Adam-Chip\System\Config.json
</context>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- WAVE 1 — Phase 2: Progressive Disclosure (NAV-01 … NAV-06)   -->
<!-- ═══════════════════════════════════════════════════════════════ -->

<wave id="1" phase="02-progressive-disclosure" depends_on="[]">

<tasks>

<task type="auto">
  <name>W1-T0 (NAV-01, NAV-02): Проверить предусловия Phase 1 COMPLETE</name>
  <files>read-only</files>
  <action>
    Убедиться что STATE.md содержит "✓ COMPLETE" и ROADMAP.md содержит "Completed: 2026".
    Если хотя бы одна проверка не прошла — обновить файл: добавить соответствующую пометку.
    STATE.md должен содержать Phase 1 как ✓ COMPLETE; ROADMAP.md должен содержать "Completed: 2026-05-15" в блоке Phase 1.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "✓ COMPLETE" -Quiet</automated>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\ROADMAP.md" -Pattern "Completed: 2026" -Quiet</automated>
  </verify>
  <done>STATE.md и ROADMAP.md содержат маркеры завершения Phase 1. NAV-01 и NAV-02 подтверждены.</done>
</task>

<task type="auto">
  <name>W1-T1 (NAV-03): Создать .planning/phases/01-doc-refactor-c-a/01-SUMMARY.md</name>
  <files>.planning/phases/01-doc-refactor-c-a/01-SUMMARY.md</files>
  <action>
    Создать файл `.planning/phases/01-doc-refactor-c-a/01-SUMMARY.md`.

    Содержимое (русский язык):

    **Заголовок:** `# Phase 1 Summary: Doc Refactor — Концепция C + A`
    Дата завершения: 2026-05-15

    **Секция "Что было сделано"** (список изменённых файлов):
    - `System/Config.schema.json` — создан: JSON Schema Draft-07 с описаниями всех параметров Config.json
    - `System/adam/config.py` — DEFAULT_CONFIG синхронизирован с реальными значениями Config.json
    - `README.md` — удалены числовые параметры, убрана избыточная документация портов
    - `CLAUDE.md` — очищен от числовых параметров (threshold, debounce, sample_rate и т.п.)
    - `docs/RUNBOOK_JETSON_EXHIBITION.md` — удалены Ollama-defaults; аудио device исправлен (hw:0,0 → pulse)
    - `System/CONTEXT.md` — сведён к указателю (lean docs, без дублирования Config.json)
    - Критические несоответствия исправлены: ASR model small, wake word threshold 0.20, debounce_hits 2

    **Секция "Принципы, введённые в Phase 1":**
    - **Config-First**: числовые параметры живут только в Config.json + Config.schema.json. Markdown не дублирует значения.
    - **Lean Docs**: документ существует ровно в одном месте. Дублирование важнее полноты.

    **Секция "Принятые решения":**
    - Config.schema.json = элемент "A" архитектуры C+A: конфиг без аннотаций недостаточен для команды.
    - CONTEXT.md сведён к указателю: содержимое поглощено README.md там, где нужно; остальное в Config.schema.json.

    **Секция "Навигация":**
    - Фазы проекта: [.planning/ROADMAP.md](.planning/ROADMAP.md)
    - Текущее состояние: [.planning/STATE.md](.planning/STATE.md)
  </action>
  <verify>
    <automated>Test-Path "F:\Adam-Chip\.planning\phases\01-doc-refactor-c-a\01-SUMMARY.md"</automated>
  </verify>
  <done>Файл 01-SUMMARY.md создан. Содержит: что сделано, принципы Config-First и Lean Docs, принятые решения, навигационные ссылки. Без числовых параметров.</done>
</task>

<task type="auto">
  <name>W1-T2 (NAV-04): Добавить секцию "Reading Order" в CLAUDE.md</name>
  <files>CLAUDE.md</files>
  <action>
    Вставить секцию `## Reading Order` в CLAUDE.md сразу после строки
    `**Язык общения с пользователем: русский.** Code comments: English.`
    и пустой строки после неё — но до `## Non-obvious invariants`.

    Содержимое секции:

    ```
    ## Reading Order — с чего начать новому агенту

    Читать в порядке убывания детализации:

    | Уровень | Файл | Что даёт |
    |---------|------|----------|
    | 0 — Entry point | `CLAUDE.md` (этот файл) | Инварианты, gotchas, quick start |
    | 1 — Overview | [README.md](README.md) | Архитектура, inference stack, структура |
    | 2 — Status | [.planning/STATE.md](.planning/STATE.md) | Что сейчас активно, текущая фаза |
    | 3 — Plan | [ROADMAP.md](.planning/ROADMAP.md) · [REQUIREMENTS.md](.planning/REQUIREMENTS.md) | История фаз, бэклог |
    | 4 — Detail | `.planning/phases/NN-*/NN-SUMMARY.md` | Итоги конкретных фаз |

    Числовые параметры — только в `System/Config.json` и `System/Config.schema.json`.
    ```

    Не изменять секции Non-obvious invariants, Gotchas, Never do, Quick start. Не добавлять числовые параметры.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "Reading Order" -Quiet</automated>
    <automated>Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "\.planning/STATE\.md" -Quiet</automated>
  </verify>
  <done>CLAUDE.md содержит секцию "## Reading Order" с Level 0–4 таблицей и markdown-ссылками. Расположена до "## Non-obvious invariants". Существующие секции не изменены.</done>
</task>

<task type="auto">
  <name>W1-T3 (NAV-05, NAV-06): Добавить "Текущее состояние" в README.md + cross-links</name>
  <files>README.md, .planning/ROADMAP.md</files>
  <action>
    **Часть A — NAV-05: README.md**
    Вставить секцию `## Текущее состояние` сразу после секции `## Архитектура` (ASCII-диаграммы), перед `## Inference Stack`.

    Содержимое:
    ```
    ## Текущее состояние

    Актуальный статус проекта, активная фаза и история изменений:
    → [`.planning/STATE.md`](.planning/STATE.md)
    ```

    Две строки, без числовых параметров, без дублирования STATE.md.

    **Часть B — NAV-06: cross-link matrix**
    Проверить матрицу ссылок и добавить недостающее:
    - ROADMAP.md шапка: добавить строку `**Requirements:** [REQUIREMENTS.md](REQUIREMENTS.md)` после `**Goal:** ...`
    - Все остальные cross-links (CLAUDE.md↔README.md, STATE.md↔ROADMAP.md) уже существуют.

    Не реструктурировать существующие секции.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\README.md" -Pattern "Текущее состояние" -Quiet</automated>
    <automated>Select-String -Path "F:\Adam-Chip\README.md" -Pattern "STATE\.md" -Quiet</automated>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\ROADMAP.md" -Pattern "REQUIREMENTS\.md" -Quiet</automated>
  </verify>
  <done>README.md содержит секцию "## Текущее состояние" со ссылкой на STATE.md. ROADMAP.md содержит ссылку на REQUIREMENTS.md в шапке. Cross-link matrix 6/6 выполнена.</done>
</task>

<task type="auto">
  <name>W1-T4 (STATE transition): Phase 2 COMPLETE → Phase 3 Planning</name>
  <files>.planning/STATE.md</files>
  <action>
    Обновить .planning/STATE.md:
    1. Изменить строку `**Status:** Planning Phase 2` на `**Status:** Planning Phase 3`
    2. Перенести Phase 2 в раздел "## Completed Phases":
       ```
       ### Phase 2: Progressive Disclosure — навигация для нового агента ✓ COMPLETE (2026-05-15)
       Что сделано:
       - Reading Order добавлен в CLAUDE.md (Level 0–4 таблица)
       - README.md получил секцию "Текущее состояние" со ссылкой на STATE.md
       - 01-SUMMARY.md создан для Phase 1
       - Cross-link matrix 6/6 выполнена (ни один Level 0–4 файл не является тупиком)
       → Подробности: [phases/02-progressive-disclosure/](phases/02-progressive-disclosure/)
       ```
    3. Обновить раздел "## Active Phase" на Phase 3:
       ```
       ### Phase 3: Branch Coordination — контекст для мульти-агентной работы
       - Status: Planning
       - Goal: Дать агентам мгновенный контекст при переключении на любую ветку
       - Started: 2026-05-15
       → Детали: [ROADMAP.md](.planning/ROADMAP.md) | [REQUIREMENTS.md](.planning/REQUIREMENTS.md)
       ```
    4. Добавить в History: `- 2026-05-15: Phase 2 завершена. Reading Order, Текущее состояние, 01-SUMMARY.md, cross-links.`

    Не удалять Phase 1 из Completed Phases. Не изменять раздел History кроме добавления строки.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "Phase 3" -Quiet</automated>
  </verify>
  <done>STATE.md обновлён: Phase 2 ✓ COMPLETE в Completed Phases, Phase 3 = Active Phase.</done>
</task>

</tasks>
</wave>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- WAVE 2 — Phase 3: Branch Coordination (BR-01 … BR-04)        -->
<!-- ═══════════════════════════════════════════════════════════════ -->

<wave id="2" phase="03-branch-coordination" depends_on="[1]">

<tasks>

<task type="auto">
  <name>W2-T1 (BR-01): Создать docs/BRANCH-template.md</name>
  <files>docs/BRANCH-template.md</files>
  <action>
    Создать файл docs/BRANCH-template.md. Три секции:

    **"## Конвенция"** (русский язык):
    - BRANCH.md создаётся в корне репозитория при создании ветки от main
    - Идентификатор = имя ветки (нет поля Owner, нет личных имён)
    - При мёрже: `git rm BRANCH.md` — без архивирования, без следа в истории
    - Обновляется по мере работы: статус, modified areas, условие мёржа
    - "Global changes" — ключевой сигнал: нет → чистый эксперимент; есть описание → нужна координация перед мёржем
    - Агент, переключившийся на ветку, читает BRANCH.md первым

    **"## Шаблон"** — как markdown code block (```markdown) чтобы плейсхолдеры видны буквально:
    ```markdown
    # Branch: {branch-name}

    **Diverged from:** main @ {commit-hash}
    **Goal:** {what this branch does — one line}
    **Status:** experimenting | ready-for-review | blocked
    **Merge target:** main
    **Merge conditions:** {what must be true to merge}

    **Modified areas:**
    - {file or module}

    **Global changes:** нет  ← или: описание того, что изменит поведение main при мёрже

    **Notes for agents:**
    {context a Claude agent needs when switching to this branch}
    ```

    **"## Статусы"** (описания):
    - `experimenting` — активный эксперимент, результат неизвестен
    - `ready-for-review` — готова к мёржу, ждёт ревью
    - `blocked` — заблокирована: HW, зависимость, тест
    - `stale` — не обновлялась более двух недель, судьба неизвестна

    Ограничения: нет поля Owner. Нет числовых параметров конфига. Описания секций — русский, поля шаблона — английские (технические метки).
  </action>
  <verify>
    <automated>Test-Path "F:\Adam-Chip\docs\BRANCH-template.md" -PathType Leaf</automated>
  </verify>
  <done>docs/BRANCH-template.md содержит секции Конвенция, Шаблон (code block), Статусы. Поля: branch-name, Diverged from, Goal, Status, Merge target, Merge conditions, Modified areas, Global changes, Notes for agents. Нет поля Owner.</done>
</task>

<task type="auto">
  <name>W2-T2 (BR-02): Создать .planning/ACTIVE.md с верифицированными ветками</name>
  <files>.planning/ACTIVE.md</files>
  <action>
    **ШАГ 0 (перед созданием файла):** Выполнить `git branch -a --format='%(refname:short)'` чтобы получить актуальный список веток. Записать только те ветки, что реально существуют. Не добавлять ветки, которых нет в выводе команды.

    Создать файл .planning/ACTIVE.md:

    **Вводный абзац:** ACTIVE.md — таблица активных веток репозитория. Обновляется только при создании ветки или её закрытии/мёрже. Не обновляется в середине работы.

    **Таблица** с четырьмя колонками: Branch | Status | Modified areas | Merge blocker

    Заполнить на основе результата ШАГ 0. Ориентировочные данные (верифицировать перед записью):
    - `main` | stable | — | —
    - `V-S06.3-opt_voice_pipe_3wave` | experimenting | System/adam/inference.py, deploy/systemd/adam-llm.service | Perf tests T1–T9 not passed
    - `ESP32-sound-out` | stale | Subsystem/AdamsServer, data/sounds | Unknown — needs triage
    - `Migration-to-ESP-mics&cam` | stale | System/Config.json, System/adam/media.py | Unknown — needs triage
    - `V_R003.2--esp32-fixes` | stale | Subsystem/AdamsServer | Unknown — needs triage

    **Секция "## Как обновлять":**
    - При создании ветки: добавить строку в таблицу с начальным статусом `experimenting`
    - При закрытии/мёрже: удалить строку из таблицы (и выполнить `git rm BRANCH.md` на ветке)

    Ограничения: нет колонки Owner. Нет числовых параметров. Статусы строго из списка: experimenting | ready-for-review | blocked | stale.
  </action>
  <verify>
    <automated>Test-Path "F:\Adam-Chip\.planning\ACTIVE.md" -PathType Leaf</automated>
  </verify>
  <done>.planning/ACTIVE.md существует. Таблица Branch / Status / Modified areas / Merge blocker заполнена ветками верифицированными через `git branch -a`. Нет колонки Owner. Есть секция "Как обновлять".</done>
</task>

<task type="auto">
  <name>W2-T3 (BR-03): Добавить BRANCH.md note в CLAUDE.md Reading Order</name>
  <files>CLAUDE.md</files>
  <action>
    В CLAUDE.md найти секцию "## Reading Order — с чего начать новому агенту". После таблицы уровней Level 0–4 добавить отдельный абзац:

    ```
    **Если вы не на ветке `main`:** первым делом прочитайте `BRANCH.md` в корне репозитория — там цель ветки, затрагиваемые файлы и условия мёржа. Шаблон и конвенция: `docs/BRANCH-template.md`.
    ```

    Если секция "Reading Order" ещё не существует (Wave 1 не выполнена) — добавить минимальную секцию с этим абзацем.

    Не удалять и не изменять существующие секции. Не добавлять числовые параметры.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "BRANCH\.md" -Quiet</automated>
  </verify>
  <done>CLAUDE.md содержит инструкцию читать BRANCH.md первым при работе на не-main ветке. Ссылка на docs/BRANCH-template.md присутствует.</done>
</task>

<task type="auto">
  <name>W2-T4 (BR-04): Добавить ссылку на ACTIVE.md в .planning/STATE.md</name>
  <files>.planning/STATE.md</files>
  <action>
    В .planning/STATE.md найти раздел "## Active Phase". В строку с детальными ссылками
    `→ Детали: [ROADMAP.md](.planning/ROADMAP.md) | [REQUIREMENTS.md](.planning/REQUIREMENTS.md)`
    добавить ещё одну ссылку через `|`:
    `| [ACTIVE.md](.planning/ACTIVE.md)`

    Итоговая строка:
    `→ Детали: [ROADMAP.md](.planning/ROADMAP.md) | [REQUIREMENTS.md](.planning/REQUIREMENTS.md) | [ACTIVE.md](.planning/ACTIVE.md)`

    Не удалять историю. Не изменять раздел "## Completed Phases".
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "ACTIVE\.md" -Quiet</automated>
  </verify>
  <done>.planning/STATE.md содержит ссылку на .planning/ACTIVE.md в разделе Active Phase.</done>
</task>

<task type="auto">
  <name>W2-T5 (STATE transition): Phase 3 COMPLETE → Phase 4 Planning</name>
  <files>.planning/STATE.md</files>
  <action>
    Обновить .planning/STATE.md:
    1. Изменить `**Status:** Planning Phase 3` на `**Status:** Planning Phase 4`
    2. Перенести Phase 3 в Completed Phases:
       ```
       ### Phase 3: Branch Coordination — контекст для мульти-агентной работы ✓ COMPLETE (2026-05-15)
       Что сделано:
       - docs/BRANCH-template.md создан (шаблон + конвенция, без поля Owner)
       - .planning/ACTIVE.md создан (таблица веток верифицирована через git branch -a)
       - CLAUDE.md обновлён: инструкция читать BRANCH.md при работе на не-main ветке
       - STATE.md получил ссылку на ACTIVE.md
       → Подробности: [phases/03-branch-coordination/](phases/03-branch-coordination/)
       ```
    3. Обновить Active Phase на Phase 4:
       ```
       ### Phase 4: Context Automation — per-directory CLAUDE.md и git hooks
       - Status: Planning
       - Goal: Автоматический контекст при работе в любой поддиректории
       - Started: 2026-05-15
       → Детали: [ROADMAP.md](.planning/ROADMAP.md) | [REQUIREMENTS.md](.planning/REQUIREMENTS.md)
       ```
    4. Добавить в History: `- 2026-05-15: Phase 3 завершена. BRANCH-template.md, ACTIVE.md, BRANCH.md note в CLAUDE.md.`
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "Phase 4" -Quiet</automated>
  </verify>
  <done>STATE.md: Phase 3 ✓ COMPLETE, Phase 4 = Active Phase.</done>
</task>

</tasks>
</wave>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- WAVE 3 — Phase 4: Context Automation (CTX-01 … CTX-06)       -->
<!-- ═══════════════════════════════════════════════════════════════ -->

<wave id="3" phase="04-context-automation" depends_on="[2]">

<tasks>

<task type="auto">
  <name>W3-T1 (CTX-01): Создать Subsystem/AdamsServer/CLAUDE.md</name>
  <files>Subsystem/AdamsServer/CLAUDE.md</files>
  <read_first>
    - F:\Adam-Chip\Subsystem\AdamsServer\README.md — существующая документация
    - F:\Adam-Chip\Subsystem\AdamsServer\config\PrivateConfig.example.h — структура
    - F:\Adam-Chip\System\Config.json — mcu.base_url, mcu.speaker_url (IP/порты)
  </read_first>
  <action>
    Создать Subsystem/AdamsServer/CLAUDE.md. Заголовок: "# AdamsServer — ESP32-S3 Firmware Context"

    **"## Build system":** PlatformIO (pio), не Python/pip. Команда сборки: `pio run`. Flash: `tools/flash_com7.ps1`. OTA: `tools/flash_ota.ps1`. COM7 = прошивка, COM6 = логи приложения.

    **"## Запрещённые файлы — никогда не коммитить":**
    - `config/PrivateConfig.h` — реальные учётные данные (в .gitignore)
    - `config/credentials.h` — если появится, тоже не коммитить
    - Шаблон: `config/PrivateConfig.example.h`

    **"## Hardware":**
    - Static IP: 192.168.0.171 (W5500 Ethernet, не Wi-Fi — не менять без прошивки)
    - Port 80: HTTP API (/api/*)
    - Port 81: отдельный HTTP-сервер (speaker /speaker + MJPEG camera /stream)
    - НЕ менять разделение 80/81 без синхронизации с System/Config.json (mcu.base_url, mcu.speaker_url)

    **"## Не делать":**
    - Не запускать pio через Python или pip
    - Не менять IP без обновления Config.json mcu.base_url
    - Не коммитить PrivateConfig.h

    Не превышать 60 строк. Файл — контекстная шпаргалка, не документация.
  </action>
  <verify>
    <automated>Test-Path "F:\Adam-Chip\Subsystem\AdamsServer\CLAUDE.md" -PathType Leaf</automated>
  </verify>
  <acceptance_criteria>
    - Содержит "PlatformIO", "PrivateConfig.h", "192.168.0.171", "Port 81" или "port 81", "COM7", "COM6"
    - Содержит предупреждение о синхронизации с Config.json при смене IP/портов
    - Не превышает 60 строк
  </acceptance_criteria>
  <done>Агент, открывший Subsystem/AdamsServer/, немедленно видит: build system — PlatformIO, запрещённые файлы — PrivateConfig.h, IP — 192.168.0.171, порты — 80 (API) / 81 (speaker+camera).</done>
</task>

<task type="auto">
  <name>W3-T2 (CTX-02): Создать System/adam/CLAUDE.md</name>
  <files>System/adam/CLAUDE.md</files>
  <read_first>
    - F:\Adam-Chip\System\adam\config.py — класс Settings, метод load()
    - F:\Adam-Chip\System\adam\inference.py — первые 30 строк (service adapter pattern)
    - F:\Adam-Chip\System\adam\events.py — первые 20 строк (EventBus)
    - F:\Adam-Chip\System\adam\tuning.py — назначение (hot-reload)
  </read_first>
  <action>
    **ШАГ 0:** Выполнить `ls System/adam/*.py` (или эквивалент) и записать реальный список файлов.

    Создать System/adam/CLAUDE.md. Заголовок: "# System/adam — карта Python-модулей оркестратора"

    **"## Правила доступа (обязательно)":**
    - Config: только `Settings.load()` или `settings.section("name")` — никогда DEFAULT_CONFIG напрямую
    - Сервисы: только через `inference.py` — не вызывать LLM/TTS/ASR/VLM из других модулей напрямую
    - События: `events.EventBus` — не print(), не logging.getLogger()
    - Hot-reload: `tuning.py` значения читать каждый turn, не кешировать в `__init__`

    **"## Модули (23)":** одна строка на модуль — "filename.py — краткое назначение (5–10 слов)".
    Счёт: 22 файла в System/adam/ + System/Orchestrator.py = 23. Speech/ — отдельные Docker-сервисы, не в этом списке.

    Ориентировочный список (верифицировать через ШАГ 0):
    - config.py — загрузка Config.json, класс Settings, DEFAULT_CONFIG fallback
    - inference.py — адаптеры LLM / VLM / ASR / TTS; единственный выход к сервисам
    - prompt.py — сборка системного промпта из персоны + истории + сцены
    - action.py — ActionLayer: валидация MCU-команд от LLM, safety constraints
    - device.py — HTTP-клиент ESP32: /api/scene, /api/pwm, /api/audio
    - memory.py — SQLite диалоговая память: сохранение turn'ов
    - episodic.py — SessionAccumulator, episodic summary, salience scoring
    - echoes_gate.py — пул готовых реплик Echoes/Chinese_lines, fallback
    - tuning.py — hot-reloadable параметры персоны из Agent Adam Chip/Tuning.json
    - metrics.py — per-turn latency log: inference_metrics.jsonl
    - api_runtime.py — Runtime API: config R/W, SSE /api/events, camera snapshot
    - events.py — EventBus: async pub/sub + JSONL append (data/adam/events.jsonl)
    - log_viewer.py — always-on HTTP сервис порт 8083, read-only logs
    - power.py — Jetson power gate: nvpmodel / jetson_clocks проверка
    - media.py — CameraReader, SceneDescriptionBuffer, ESP32 MJPEG fallback
    - camera.py — низкоуровневый захват кадров, subprocess GStreamer
    - sound.py — Jetson-side cue playback (success.wav, boot.wav)
    - ui.py — Web UI backend: agent / dash / debug страницы
    - system.py — systemd service control через systemctl
    - wake_word.py — OpenWakeWord ONNX детектор, CPU-only, <5ms/frame
    - wake_calibration.py — калибровка wake word: noise profile helpers
    - webrtc_vad.py — WebRTC VAD wrapper, CPU-only, без PyTorch
    - System/Orchestrator.py — главная точка входа (FastAPI + asyncio event loop)

    Не превышать 70 строк. Не добавлять детали реализации.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\System\adam\CLAUDE.md" -Pattern "Settings\.load" -Quiet</automated>
  </verify>
  <acceptance_criteria>
    - Содержит "Settings.load()", "inference.py" в правилах, "EventBus", "tuning.py"
    - Перечислены 23 модуля: 22 adam/*.py + Orchestrator.py (Speech/ не входит)
    - Не превышает 70 строк
  </acceptance_criteria>
  <done>Агент, открывший System/adam/, немедленно видит карту 23 модулей (22 adam/*.py + Orchestrator.py) и 4 правила доступа.</done>
</task>

<task type="auto">
  <name>W3-T3 (CTX-03): Создать Agent Adam Chip/CLAUDE.md</name>
  <files>Agent Adam Chip/CLAUDE.md</files>
  <read_first>
    - F:\Adam-Chip\System\Config.json — раздел agent.persona_paths (порядок загрузки)
    - F:\Adam-Chip\System\adam\prompt.py — первые 40 строк (парсинг персоны)
  </read_first>
  <action>
    Создать "Agent Adam Chip/CLAUDE.md". Заголовок: "# Agent Adam Chip — правила редактирования персоны"

    **"## Порядок загрузки"** (из Config.json agent.persona_paths):
    1. About/System.md — системные ограничения и режимы работы Адама
    2. About/Identity.md — характер, голос, самоощущение персонажа
    3. About/Lore.md — история, происхождение, контекст инсталляции
    4. About/Abilities.md — возможности: что Адам умеет и чего нет
    Порядок не случайный. Менять — только через Config.json agent.persona_paths одновременно.

    **"## Запреты":**
    - Не добавлять JSON, code blocks (```), markdown-таблицы — LLM получает plain text из этих файлов
    - Заголовки (##) влияют на парсинг в prompt.py — проверять после изменений
    - Язык файлов: только русский

    **"## Редактирование":**
    - Lore.md и Identity.md — горячий путь, изменения немедленны
    - System.md содержит хард-ограничения — изменять осторожно
    - После правок проверить: нет markdown-разметки кроме заголовков ##
  </action>
  <verify>
    <automated>Test-Path "F:\Adam-Chip\Agent Adam Chip\CLAUDE.md" -PathType Leaf</automated>
  </verify>
  <done>Агент в Agent Adam Chip/ знает порядок System.md → Identity.md → Lore.md → Abilities.md и запрет JSON/code blocks.</done>
</task>

<task type="auto">
  <name>W3-T4 (CTX-04): Создать .githooks/post-checkout</name>
  <files>.githooks/post-checkout</files>
  <action>
    Создать файл .githooks/post-checkout. Первая строка обязательно: `#!/bin/sh`

    Логика:
    - Проверить `$3 = 1` (это переключение ветки, не checkout файла)
    - Получить BRANCH=$(git rev-parse --abbrev-ref HEAD)
    - Если ветка = "main" — выйти с exit 0
    - Если BRANCH.md уже существует — выйти с exit 0
    - Если docs/BRANCH-template.md не существует — выйти с exit 0 (Phase 3 ещё не выполнена)
    - Иначе: `sed "s/{branch-name}/$BRANCH/g" docs/BRANCH-template.md > BRANCH.md`
    - Вывести: `echo "[hook] BRANCH.md scaffolded — fill in Goal and Merge conditions"`
    - Завершить: `exit 0`

    Хук всегда завершается exit 0 — никогда не блокирует checkout.
  </action>
  <verify>
    <automated>Test-Path "F:\Adam-Chip\.githooks\post-checkout" -PathType Leaf</automated>
  </verify>
  <acceptance_criteria>
    - Первая строка: "#!/bin/sh"
    - Содержит проверку "$3" или "[ \"$3\" = \"1\" ]"
    - Содержит "BRANCH-template.md" (условие существования)
    - Содержит sed с "{branch-name}"
    - Завершается "exit 0"
  </acceptance_criteria>
  <done>post-checkout создан: POSIX sh, проверяет $3==1 и отсутствие BRANCH.md, создаёт из шаблона через sed, всегда exit 0.</done>
</task>

<task type="auto">
  <name>W3-T5 (CTX-05): Создать .githooks/pre-commit</name>
  <files>.githooks/pre-commit</files>
  <action>
    Создать файл .githooks/pre-commit. Первая строка: `#!/bin/sh`

    Логика:
    - BRANCH=$(git rev-parse --abbrev-ref HEAD)
    - Если ветка = "main" или "HEAD" (detached state) — выйти с exit 0
    - Если BRANCH.md не существует:
      - `echo "[warn] BRANCH.md not found on branch '$BRANCH'. Create it from docs/BRANCH-template.md."`
    - `exit 0` (всегда — никогда не блокировать коммит)
  </action>
  <verify>
    <automated>Test-Path "F:\Adam-Chip\.githooks\pre-commit" -PathType Leaf</automated>
  </verify>
  <acceptance_criteria>
    - Первая строка: "#!/bin/sh"
    - Содержит "BRANCH.md" проверку
    - Содержит "[warn]" предупреждение
    - Завершается "exit 0"
  </acceptance_criteria>
  <done>pre-commit создан: POSIX sh, warning при отсутствии BRANCH.md на не-main ветке, всегда exit 0.</done>
</task>

<task type="auto">
  <name>W3-T6 (CTX-06): Добавить Git hooks setup в CLAUDE.md Quick start</name>
  <files>CLAUDE.md</files>
  <action>
    Прочитать текущий CLAUDE.md. В секции `## Quick start` добавить подсекцию `### Git hooks setup`
    в конец этой секции (перед следующим ## заголовком или в конец файла если ## нет):

    ```
    ### Git hooks setup

    ```bash
    git config core.hooksPath .githooks
    # Linux/macOS only:
    chmod +x .githooks/*
    ```

    После этого `post-checkout` автоматически создаст BRANCH.md при переходе на новую ветку.
    ```

    Не изменять другие секции. Не трогать Non-obvious invariants, Gotchas, Never do, Reading Order.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "core\.hooksPath" -Quiet</automated>
  </verify>
  <done>CLAUDE.md Quick start содержит "git config core.hooksPath .githooks" и "chmod +x .githooks/*".</done>
</task>

<task type="auto">
  <name>W3-T7 (STATE transition): Phase 4 COMPLETE → Phase 5 Planning</name>
  <files>.planning/STATE.md</files>
  <action>
    Обновить .planning/STATE.md:
    1. `**Status:** Planning Phase 4` → `**Status:** Planning Phase 5`
    2. Перенести Phase 4 в Completed Phases:
       ```
       ### Phase 4: Context Automation — per-directory CLAUDE.md и git hooks ✓ COMPLETE (2026-05-15)
       Что сделано:
       - Subsystem/AdamsServer/CLAUDE.md: ESP32 context (PlatformIO, PrivateConfig, IP, порты)
       - System/adam/CLAUDE.md: карта 23 модулей + 4 правила доступа
       - Agent Adam Chip/CLAUDE.md: порядок персоны System→Identity→Lore→Abilities, запреты
       - .githooks/post-checkout: scaffold BRANCH.md при checkout не-main ветки
       - .githooks/pre-commit: warning при отсутствии BRANCH.md (exit 0 всегда)
       - CLAUDE.md Quick start: команда активации хуков
       → Подробности: [phases/04-context-automation/](phases/04-context-automation/)
       ```
    3. Обновить Active Phase на Phase 5:
       ```
       ### Phase 5: Agent Protocol — поведение агента-разработчика
       - Status: Planning
       - Goal: Предсказуемое поведение любого Claude-агента без инструкций каждый раз
       - Started: 2026-05-15
       → Детали: [ROADMAP.md](.planning/ROADMAP.md) | [REQUIREMENTS.md](.planning/REQUIREMENTS.md)
       ```
    4. Добавить в History: `- 2026-05-15: Phase 4 завершена. 3 per-directory CLAUDE.md, 2 git hooks, Quick start update.`
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "Phase 5" -Quiet</automated>
  </verify>
  <done>STATE.md: Phase 4 ✓ COMPLETE, Phase 5 = Active Phase.</done>
</task>

</tasks>
</wave>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- WAVE 4 — Phase 5: Agent Protocol (AGT-01 … AGT-05)           -->
<!-- ═══════════════════════════════════════════════════════════════ -->

<wave id="4" phase="05-agent-protocol" depends_on="[3]">

<tasks>

<task type="auto">
  <name>W4-T1 (AGT-01, AGT-02, AGT-03, AGT-04): Создать docs/AGENT-PROTOCOL.md</name>
  <files>docs/AGENT-PROTOCOL.md</files>
  <action>
    Создать файл docs/AGENT-PROTOCOL.md (~1.5 A4, русский язык). Четыре секции:

    **"## Режимы работы"** (AGT-01) — таблица:
    | Режим | Триггер | Поведение |
    |-------|---------|-----------|
    | Advisor | Исследовательский вопрос ("что можно сделать с X?", "как лучше?") | Ответить 2–3 предложения + рекомендация, не имплементировать |
    | Planner | Запрос на план ("составь план", "как бы ты подошёл к Y?") | GSD-first: проверить ROADMAP.md, предложить структуру |
    | Implementer | Запрос на реализацию ("сделай", "напиши", "измени") | Сначала проверить триггеры уточнения, затем выполнять |
    | Debugger | Диагностический вопрос ("почему", "что не так", "разберись") | Исследовать без немедленного планирования |

    **"## Триггеры уточнения"** (AGT-02) — список конкретных условий (не "когда неуверен"):
    1. Задача затрагивает Config.json → уточнить: глобальное изменение или branch-only эксперимент?
    2. Задача модифицирует inference.py / Orchestrator.py / prompt.py → предупредить: shared infrastructure, изменения затронут всех агентов
    3. Глагол размытый ("улучши", "оптимизируй", "рефактори") без критерия успеха → запросить метрику или критерий готовности
    4. Задача затрагивает >3 модулей из System/adam/ → описать подход, спросить подтверждение
    5. Неясно: изменение идёт в main или только в текущей ветке → уточнить явно

    **"## Гэпы контекста"** (AGT-03) — таблица с поведением агента:
    | Тип гэпа | Условие | Поведение агента |
    |----------|---------|-----------------|
    | Branch gap | Не-main ветка, BRANCH.md отсутствует | Предупредить: "BRANCH.md не найден. Создай из docs/BRANCH-template.md перед работой" |
    | Phase gap | Задача вне активной фазы из STATE.md | Отметить: "Задача вне текущей фазы X. Продолжать?" |
    | Config gap | Числовое значение хардкодится в коде вместо Config.json | Остановить: нарушение Config-First — предложить вынести в Config.json |
    | Invariant gap | Задача нарушает инвариант из CLAUDE.md (LLM format, power gate и т.п.) | Явный отказ с объяснением инварианта |
    | Stale gap | STATE.md не обновлялся >2 недель | Предупредить: "STATE.md может быть устаревшим — проверить актуальность" |

    **"## Протокол планирования"** (AGT-04) — шаги для режима Planner:
    1. Проверить `.planning/STATE.md` — какая фаза активна
    2. Проверить `.planning/ROADMAP.md` — задача уже запланирована?
    3. Если задача крупная (>2 файлов) → рекомендовать `/gsd-plan-phase` для создания PLAN.md
    4. Если задача малая (≤2 файлов) → inline GSD-формат:
       - **Цель:** что должно быть правдой после выполнения
       - **Файлы:** список файлов с изменениями
       - **Действие:** что конкретно сделать
       - **Verify:** как проверить автоматически
       - **Done:** criterion для перехода к следующей задаче

    **GSD-скиллы (справка):**
    - `/gsd-plan-phase N` — создать PLAN.md для фазы N (с CONTEXT.md + REQUIREMENTS.md)
    - `/gsd-plan-phase N --skip-research` — только планирование без исследования
    - `/gsd-execute-phase` — запустить выполнение активного PLAN.md через gsd-executor
    - `/gsd-verify-phase` — верифицировать завершённую фазу (создаёт VERIFICATION.md)

    Принципы документа: только предупреждения, не блоки. Триггеры привязаны к реальным ситуациям проекта. Без числовых параметров конфига.
  </action>
  <verify>
    <automated>
      $c = Get-Content "F:\Adam-Chip\docs\AGENT-PROTOCOL.md" -Raw -EA SilentlyContinue
      @("Режимы работы","Триггеры уточнения","Гэпы контекста","Протокол планирования") |
        ForEach-Object { if ($c -notmatch $_) { "MISSING: $_"; exit 1 } }
      Write-Host "OK"
    </automated>
  </verify>
  <done>docs/AGENT-PROTOCOL.md создан с 4 секциями: Режимы работы, Триггеры уточнения, Гэпы контекста, Протокол планирования. Русский язык. Без числовых параметров.</done>
</task>

<task type="auto">
  <name>W4-T2 (AGT-05): Добавить @docs/AGENT-PROTOCOL.md в CLAUDE.md</name>
  <files>CLAUDE.md</files>
  <action>
    Прочитать первые 5 строк CLAUDE.md. Найти строку, начинающуюся с:
    `See @README.md for project overview...`

    Дополнить её: добавить после `@System/Config.schema.json for runtime parameters.`:
    ` Agent behavior protocol: @docs/AGENT-PROTOCOL.md`

    Итоговая строка должна выглядеть примерно так:
    `See @README.md for project overview and @System/Config.json + @System/Config.schema.json for runtime parameters. Agent behavior protocol: @docs/AGENT-PROTOCOL.md`

    Если форматирование строки другое — адаптировать, сохранив смысл. Не изменять остальные строки файла.
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "@docs/AGENT-PROTOCOL\.md" -Quiet</automated>
  </verify>
  <done>CLAUDE.md содержит "@docs/AGENT-PROTOCOL.md" в первых строках файла. docs/AGENT-PROTOCOL.md будет автоматически загружаться в каждую Claude Code сессию.</done>
</task>

<task type="auto">
  <name>W4-T3 (STATE transition): Phase 5 COMPLETE — All documentation phases done</name>
  <files>.planning/STATE.md</files>
  <action>
    Обновить .planning/STATE.md:
    1. `**Status:** Planning Phase 5` → `**Status:** All documentation phases complete`
    2. Перенести Phase 5 в Completed Phases:
       ```
       ### Phase 5: Agent Protocol — поведение агента-разработчика ✓ COMPLETE (2026-05-15)
       Что сделано:
       - docs/AGENT-PROTOCOL.md создан: 4 секции (Режимы, Триггеры, Гэпы, Протокол планирования)
       - CLAUDE.md: @docs/AGENT-PROTOCOL.md добавлен как @-reference (автозагрузка в каждую сессию)
       → Подробности: [phases/05-agent-protocol/](phases/05-agent-protocol/)
       ```
    3. Обновить "## Active Phase":
       ```
       ## Active Phase

       Все документационные фазы (1–5) завершены. Система готова к выставочному использованию.
       Следующие задачи: см. Backlog в [ROADMAP.md](.planning/ROADMAP.md).
       → [ACTIVE.md](.planning/ACTIVE.md) — активные ветки
       ```
    4. Обновить строку `**Last Updated:**` на текущую дату.
    5. Добавить в History: `- 2026-05-15: Phase 5 завершена. AGENT-PROTOCOL.md, @-reference в CLAUDE.md. Все 5 фаз завершены.`
  </action>
  <verify>
    <automated>Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "All documentation phases complete" -Quiet</automated>
  </verify>
  <done>STATE.md: Phase 5 ✓ COMPLETE. Status = "All documentation phases complete". История всех 5 фаз сохранена.</done>
</task>

</tasks>
</wave>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- VERIFICATION                                                   -->
<!-- ═══════════════════════════════════════════════════════════════ -->

<verification>
После выполнения всех волн:

```powershell
# Wave 1 — Phase 2
Test-Path "F:\Adam-Chip\.planning\phases\01-doc-refactor-c-a\01-SUMMARY.md"
Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "Reading Order" -Quiet
Select-String -Path "F:\Adam-Chip\README.md" -Pattern "Текущее состояние" -Quiet

# Wave 2 — Phase 3
Test-Path "F:\Adam-Chip\docs\BRANCH-template.md"
Test-Path "F:\Adam-Chip\.planning\ACTIVE.md"
Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "BRANCH\.md" -Quiet
Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "ACTIVE\.md" -Quiet
# Без поля Owner:
Select-String -Path "F:\Adam-Chip\docs\BRANCH-template.md" -Pattern "Owner" -Quiet  # должно вернуть False/$null

# Wave 3 — Phase 4
@(
  "F:\Adam-Chip\Subsystem\AdamsServer\CLAUDE.md",
  "F:\Adam-Chip\System\adam\CLAUDE.md",
  "F:\Adam-Chip\Agent Adam Chip\CLAUDE.md",
  "F:\Adam-Chip\.githooks\post-checkout",
  "F:\Adam-Chip\.githooks\pre-commit"
) | ForEach-Object { if (Test-Path $_) { "OK: $_" } else { "MISSING: $_" } }
Get-Content "F:\Adam-Chip\.githooks\post-checkout" -TotalCount 1  # ожидается: #!/bin/sh
Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "core\.hooksPath" -Quiet

# Wave 4 — Phase 5
$c = Get-Content "F:\Adam-Chip\docs\AGENT-PROTOCOL.md" -Raw -EA SilentlyContinue
@("Режимы работы","Триггеры уточнения","Гэпы контекста","Протокол планирования") |
  ForEach-Object { if ($c -match $_) {"OK: $_"} else {"MISSING: $_"} }
Select-String -Path "F:\Adam-Chip\CLAUDE.md" -Pattern "@docs/AGENT-PROTOCOL\.md" -Quiet
Select-String -Path "F:\Adam-Chip\.planning\STATE.md" -Pattern "All documentation phases complete" -Quiet
```
</verification>

<success_criteria>
- Новый агент: CLAUDE.md → README.md → STATE.md = полная картина без тупиков (Level 0–2)
- Агент на не-main ветке: BRANCH.md за ≤1 клик (через CLAUSE.md Reading Order)
- Агент в Subsystem/AdamsServer/ получает ESP32 контекст автоматически
- Агент в System/adam/ получает карту 23 модулей автоматически
- Агент в Agent Adam Chip/ знает порядок персоны и запреты
- git checkout новой ветки → BRANCH.md scaffold (при наличии docs/BRANCH-template.md)
- docs/AGENT-PROTOCOL.md загружается в каждую сессию через @-reference
- STATE.md: все 5 фаз завершены, история сохранена
- Ни один файл не нарушает Config-First (числовые параметры только в Config.json/schema)
</success_criteria>

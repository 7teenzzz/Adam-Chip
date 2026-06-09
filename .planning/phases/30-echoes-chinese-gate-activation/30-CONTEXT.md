# Phase 30: Echoes/Chinese Gate Activation - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning
**Source:** Функциональный анализ системы памяти + диалог по улучшению инжектов (this session)
**Branch:** `MemoryFixes`

<domain>
## Phase Boundary

Заставить пулы Echoes (`Agent-Adam-Chip/About/Echoes.md`) и Chinese
(`Agent-Adam-Chip/About/Chinese_lines.md`) реально инжектиться в диалог. Это
закрывает цель пользователя «использовать все файлы из папки About в диалоге».

**Что входит:**
- Переработка матчинга/выбора в `System/adam/echoes_gate.py` (слои A, B, C, D)
- Прокидка окна истории и тем в gate из `System/Orchestrator.py`
- Активация Chinese-пула + `ru_hint` для LLM
- Новые параметры в `System/Config.json` + `System/Config.schema.json`
- Тесты gate

**Что НЕ входит (deferred):**
- Pre-rendered wav-озвучка китайских фраз по `audio_id`
  (`{DATA_DIR}/audio/chinese/{id}.wav`) — отдельная фаза, требует нового кода в
  `inference.py`/`Orchestrator.py` для TTS-плейбека
- Полноценный LLM-driven mood (это Phase 19) — здесь только минимальная
  починка/удаление мёртвой проводки mood
- Замена tag/tfidf-матчера на нейросетевые эмбеддинги (это Phase 20)
</domain>

<current_state>
## Как работает сейчас (результат анализа)

### Что из About реально попадает в диалог

| Файл | Канал | Механизм | Статус |
| --- | --- | --- | --- |
| System.md / Identity.md / Lore.md / Abilities.md | persona (system-промпт) | `PromptBuilder._load_persona()` конкатенирует все 4 файла, кэш по mtime | ✅ работает 100% turn'ов |
| Echoes.md | gate-инжект `[hint]` | `EchoGate` + `tuning.echoes` | 🟡 включён, почти никогда не срабатывает |
| Chinese_lines.md | gate-инжект `[hint]` | `EchoGate` (тот же класс) + `tuning.chinese` | 🔴 выключен (`enabled=false`) |

### Сборка промпта (`PromptBuilder.build_messages`, prompt.py)

1. `system[0]` — персона (4 файла About, склейка через `\n\n`)
2. `system[1]` — `[INTERNAL_CONTEXT]`: `[ctx.memory]` (diary.md) → `[ctx.recent_visitors]` → `[ctx.vision]` → `[ctx.sensors]`
3. история диалога (limit `tuning.prompt.history_turns`)
4. user = `[hint] <echo>` + транскрипт зрителя

### Echo-gate цепочка (`echoes_gate.py:maybe_inject`)

1. `turn_counter++`; `tuning.enabled` check
2. global cooldown (echoes 12 turns / chinese 30 turns)
3. per-id cooldown (7 дней, через `episodic_memory.all_recent_uses`)
4. `mood_block` — **инертен** (см. находку 2)
5. tag-match score ≥ `match_threshold` (echoes 0.55 / chinese 0.65)
6. случайный бросок против `weight × weight_multiplier`

## Корневые находки

**Находка 1 — мост уже существует, но не подключён.**
`SessionAccumulator.note_turn()` (episodic.py:158-162) уже нормализует речь
зрителя через `theme_clusters`: «одиноко» → тема `одиночество`. Вызывается в
Orchestrator.py:2519 **до** gate (:2539) — значит `acc.themes` на момент инжекта
уже содержит нормализованные темы. А gate в это же время матчит тег
`одиночество` как подстроку против сырого «мне одиноко» → False. Идеальное
семантическое совпадение проваливается. Многие теги карточек (`одиночество`,
`пустота`, `память`, `время`) буквально совпадают с именами/ключами кластеров.

**Находка 2 — две мёртвые проводки.**
`mood` жёстко прибит к `"neutral"` (Orchestrator.py:2534-2535), `_resolve_mood`
возвращает только `overload`/`neutral`. → `mood_block` (`hostile`/`overload` в
карточках) полностью инертен. `adam_state` передаётся в `maybe_inject`, но в теле
метода не используется (echoes_gate.py:277 проверяет только `mood`).

**Находка 3 — оба матчера сравнивают (транскрипт зрителя) × (теги карточки).**
И tag, и tfidf-матчер (corpus строится только из тегов: `corpus = [_tokenize("
".join(e.tags)) ...]`) сравнивают слова зрителя с тегами-образами Адама. Зритель
не произносит «коридор»/«эскалатор»/«物是人非» → score ≈ 0.
</current_state>

<decisions>
## Implementation Decisions (LOCKED)

### Scope — четыре слоя (подтверждено пользователем)

**Слой A — тематический мост + окно истории (корневой фикс recall)**
- `_score_match` матчит теги против `{acc.themes} ∪ {ключевые слова кластеров}`,
  а не против сырого транскрипта
- Источник матча — взвешенное окно последних N реплик (зритель + Адам), не одна
  реплика. Текущая реплика зрителя — макс. вес, прошлые + реплики Адама —
  затухание
- Чистые образы-теги (не в кластерах) сохраняются для редких буквальных матчей

**Слой B — мягкий вероятностный движок**
- Замена жёсткого `match_threshold` на `final = thematic_match × weight × recency_decay`
- Кандидаты выше низкого пола → взвешенно-случайный выбор (не top-1 по обрыву)
- RNG остаётся seedable (echoes_gate.py:211) для детерминизма тестов
- Редкость держится на cooldown'ах, не на пороге

**Слой C — спонтанный канал**
- Независимый низковероятный путь инжекта по внутренним сигналам: длинная пауза
  зрителя / `acc.turn_count` / N-й turn
- Выбор карточки по `weight` без тематического матча («память всплывает сама»)
- Соблюдает те же cooldown'ы и анти-повтор

**Слой D — разнообразие + починка mood**
- Анти-повтор семантического кластера за сессию (не только per-id cooldown):
  не `коридор → лестница → эскалатор` подряд
- Mood: либо вычислять реально и использовать, либо удалить инертный
  `mood_block` из расчёта + убрать неиспользуемый `adam_state` из сигнатуры

### Chinese-активация (подтверждено пользователем)
- `tuning.chinese.enabled=true` + ослабление порога
- `ru_hint` прокидывается в `[hint]` для LLM как смысловая подсказка (Silero
  `v5_5_ru` не озвучит иероглифы) — наряду с самой китайской фразой
- Озвучка pre-rendered wav — DEFERRED

### Инварианты проекта (MUST hold)
- Config-First: все новые числа в `Config.json` + `Config.schema.json`
- LLM = чистый русский текст; `[hint]` — служебная подсказка, не диалог
- Hot-reload: tuning читается каждый turn, не кешируется в `__init__`
- Доступ к сервисам только через `inference.py`; события через `EventBus`

### Claude's Discretion
- Точная форма recency_decay (линейная / экспоненциальная)
- Структура хранения «использованных кластеров за сессию» (в `EchoGate` vs
  `SessionAccumulator`)
- Имена и дефолты новых Config-параметров (с учётом схемы)
- Решение revive-vs-remove для mood (по минимальной сложности; полноценный
  mood — Phase 19)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Gate core
- `System/adam/echoes_gate.py` — `EchoGate`, `maybe_inject`, `_score_match`,
  `_score_tag`, `_score_tfidf`, `parse_echoes_file`, `TfIdfMatcher`
- `System/adam/episodic.py` — `SessionAccumulator` (`themes`, `note_turn`,
  `adam_state`, `note_echo_used`, `note_chinese_used`)
- `System/adam/memory.py` — `EpisodicMemory` (`all_recent_uses`,
  `record_echo_used`, gate-логи)

### Orchestration / prompt
- `System/Orchestrator.py` — инициализация gate (:108-118), вызов инжекта
  (:2519 note_turn, :2533-2565 echoes/chinese gate, :2534-2535 dead mood),
  `_resolve_mood` (:249-258), `_format_recent_episodic`
- `System/adam/prompt.py` — `PromptBuilder.build_messages`, как `echo_hint`
  попадает в user-сообщение (:204-208)
- `System/adam/tuning.py` — `EchoesTuning`, `ChineseTuning` pydantic-модели

### Config / persona
- `System/Config.json` — секции `tuning.echoes`, `tuning.chinese`,
  `tuning.memory.theme_clusters`
- `System/Config.schema.json` — описания параметров echoes/chinese
- `Agent-Adam-Chip/About/Echoes.md` — пул (20 карточек, YAML-frontmatter)
- `Agent-Adam-Chip/About/Chinese_lines.md` — пул (7 карточек, `audio_id`/`ru_hint`)
- `Agent-Adam-Chip/CLAUDE.md` — правила персоны (запрет markdown в About-файлах)
</canonical_refs>

<specifics>
## Specific Ideas

- `theme_clusters` уже содержит 8 кластеров (память, смерть, тесей, одиночество,
  создатель, восприятие, сознание, страх) — это готовый словарь для слоя A
- Echo-теги, прямо совпадающие с кластерами: `одиночество`, `пустота`, `память`,
  `время`, `прошлое` — дадут матч сразу после слоя A
- Chinese-теги тоже тематические (`память`, `перемена`, `время`, `тишина`,
  `симбиоз`, `сознание`) — слой A работает и для них
- `recurring`/`recent_visitors` инжект требует полного ФИО (`_extract_visitor_name`
  отбрасывает однословные) — не трогаем в этой фазе, но учитываем что это
  отдельный канал
</specifics>

<deferred>
## Deferred Ideas

- Pre-rendered wav-озвучка китайских фраз (`audio_id` → TTS-плейбек) — отдельная
  фаза, новый код в `inference.py`/`Orchestrator.py`
- Полноценный LLM-driven mood — Phase 19 (Mood LLM-driven)
- Нейросетевые эмбеддинги вместо tag/tfidf — Phase 20 (Memory Wave 2)
- Расширение пулов до целевых объёмов (Echoes 20→30, Chinese 7→15-20) — контентная
  задача, не код
</deferred>

---

*Phase: 30-echoes-chinese-gate-activation*
*Context gathered: 2026-06-07 (функциональный анализ системы памяти)*

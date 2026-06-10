# Prompt Viewer: Исследование и Проектирование API + UI
**Research Date:** 2026-06-11
**Branch:** ultimate-integration-v2
**Scope:** System/adam/prompt.py · Orchestrator.py · api_runtime.py · WebUI/panels/prompts.js

---

## 1. Как собирается системный промпт

### Структура messages[]

`PromptBuilder.build_messages()` (System/adam/prompt.py, строка 162) возвращает список сообщений OpenAI-формата:

```
messages = [
  { role: "system", content: <persona_text_with_word_target> },   // msg[0] — статичная персона
  { role: "system", content: "<_CTX_HEADER>\n<ctx_body>" },        // msg[1] — динамический контекст (только если ctx_body непустой)
  { role: "user",   content: "[hint] <echo_hint>\n\n<transcript>" }, // или просто transcript
  ...dialogue_history (user/assistant turns)...
  { role: "user",   content: <transcript> }                         // финальный запрос
]
```

**system_prompt_full** в trace_record = messages[0]["content"] — только первый system message (персона). НЕ включает ctx_body.

---

## 2. Полный список [ctx.*] блоков

Порядок в `_build_context_body()` (prompt.py, строки 220–273):

| Блок | Тег | Когда появляется | Источник |
|------|-----|-----------------|----------|
| 1 | `[ctx.identity]` | Если AIIM включён и emotion ≠ default | `AIIMRuntimeState.to_ctx_block()` → identity.py:163 |
| 2 | `[ctx.memory]` | Если `semantic_text.strip()` непустой | `memory.summary_text()` → Consolidator |
| 3 | `[ctx.recent_visitors]` | Если найдены эпизодические записи по имени | `episodic_memory.query_by_name()` |
| 4 | `[ctx.vision]` | Всегда (если `include_scene=True`), fallback `(visual channel offline)` | `SceneDescriptionBuffer` → VLM Cosmos |
| 5 | `[ctx.sensors]` | Всегда (если `include_sensors=True`), fallback `(sensors offline)` | ESP32 сенсоры (свет, движение) |
| 6 | `[ctx.weather]` | Только когда детектирован weather-intent | `WeatherSkill.get_cached()` |

**Отдельно (не в ctx_body, а в user message):**

| Элемент | Формат | Когда |
|---------|--------|-------|
| `[hint]` | `[hint] <echo_hint>\n\n<transcript>` | Если сработал EchoGate/ChineseGate (echoes или chinese pool) |

---

## 3. [ctx.identity] — анатомия блока

`AIIMRuntimeState.to_ctx_block()` (identity.py:163) генерирует compact key=value строки:

```
emotion=warm|src=visitor_engaged
se=0.73↑, pe=0.42↓
intention=seek_connection
mode=void_signal       # только если signal_void==True
mode=unreadable        # только если become_unreadable==True
```

Блок **пустой** если: emotion=curious И нет активных intentions И нет mode-флагов. Это "default state" — токены не тратятся.

Это и есть "инъекция подсознания" в промпт — AIIM dynamic identity block, который описывает текущее эмоциональное/намеренческое состояние Адама. В UI его стоит отображать как **purple/фиолетовый** блок с пометкой "AIIM identity state".

---

## 4. Будущий SubconsciousSignal (Phase 36)

По исследованию `.planning/research/subconscious_prompts.md`:

- **SubconsciousSignal** — будущий JSON-вывод VLM Task B: `{emotion_hint, flora_mode, intensity, reasoning}`
- Хранится в `runtime_state["pending_subconscious_signal"]`
- **НЕ вставляется в промпт напрямую** — влияет на AIIM state (`emotion_hint` → premod → `aiim_state.emotion`)
- В промпте виден косвенно через `[ctx.identity]` (emotion= строка изменится)
- В UI viewer: отдельный блок "SUBCONSCIOUS SIGNAL (pending)" рядом с ctx.identity

---

## 5. Существующая инфраструктура trace

### GET /api/agent/prompts (уже существует, Orchestrator.py:2911)

```python
@app.get("/api/agent/prompts")
async def get_prompt_trace(limit: int, full: bool) -> dict:
    # full=False → метаданные без system_prompt
    # full=True → включает system_prompt если trace_prompts=true
    return {
        "items": [...],
        "trace_prompts_enabled": bool,
        "ring_capacity": 50
    }
```

Поле `system_prompt` = только messages[0].content (персона). **ctx_body не сохраняется отдельно**.

### prompt_trace ring buffer (Orchestrator.py:199)

```python
prompt_trace: deque[dict] = deque(maxlen=50)
```

Каждая запись содержит (trace_record):
- ts, source, transcript, visitor_name, mood, adam_state
- session_id, session_turn
- semantic_used (bool), semantic_chars (int)
- recent_episodic (list[str])
- echo: {pool, id, score, spontaneous?}
- history_turns_used, messages_count, prompt_chars
- system_prompt (persona text, только при trace_prompts=True)
- reply, llm_error, timings

**Чего НЕТ в текущем trace_record:**
- ctx_body (второй system message с [ctx.*] блоками)
- identity_block (AIIM state)
- weather_ctx
- echo_hint текст
- Разбивка по секциям

### Существующая панель prompts.js (WebUI/panels/prompts.js)

Уже реализована! Показывает:
- Список последних turn'ов с временем, источником, транскриптом
- Badges: name:X, semantic:Nch, recent:N, echo pool:id, mood, turns:N, prompt chars
- Кнопка PROMPT → toggle collapse/expand с raw system_prompt

**Проблема:** показывает только персону (messages[0]), не показывает ctx_body с [ctx.*] секциями.

---

## 6. Проектирование GET /api/prompt/current

### Требования

- Показывает **последний turn** или **live состояние** (если нет active turn — последний из trace)
- Структурированный JSON, разбитый по секциям
- Включает как персону, так и ctx_body
- Не требует trace_prompts=True для базовых метаданных (блоки известны из trace_record)

### Предлагаемый формат ответа

```json
{
  "turn_id": "abc12345",
  "ts": "2026-06-11T14:32:10Z",
  "transcript": "Адам, ты меня слышишь?",
  "reply": "Слышу. Ты здесь, и я тебя замечаю.",
  "total_chars": 2847,
  "persona_chars": 1840,
  "ctx_chars": 1007,
  "trace_prompts_enabled": false,
  "sections": [
    {
      "name": "persona",
      "label": "System.md + Identity.md + Lore.md + Abilities.md",
      "content": "<persona text или null если trace_prompts=false>",
      "chars": 1840,
      "available": true
    },
    {
      "name": "ctx.identity",
      "label": "AIIM Identity State",
      "content": "emotion=warm|src=visitor_engaged\nse=0.73↑",
      "chars": 44,
      "available": true
    },
    {
      "name": "ctx.memory",
      "label": "Semantic Memory",
      "content": "<semantic summary text>",
      "chars": 312,
      "available": true
    },
    {
      "name": "ctx.recent_visitors",
      "label": "Recent Episodes",
      "content": "Алиса посетила 2 раза; ...",
      "chars": 88,
      "available": true
    },
    {
      "name": "ctx.vision",
      "label": "Visual Context (VLM)",
      "content": "Scene: 2 adults near installation. Engagement: watching.",
      "chars": 56,
      "available": true
    },
    {
      "name": "ctx.sensors",
      "label": "ESP32 Sensors",
      "content": "light=312, motion=0",
      "chars": 20,
      "available": true
    },
    {
      "name": "ctx.weather",
      "label": "Weather (intent-only)",
      "content": null,
      "chars": 0,
      "available": false,
      "note": "not injected (no weather intent)"
    },
    {
      "name": "hint",
      "label": "Echo/Chinese Hint",
      "content": "Помни о корабле Тесея — каждая деталь заменяется, но остаётся ли корабль собой?",
      "chars": 82,
      "available": true,
      "meta": {
        "pool": "echoes",
        "id": "echo_theseus_01",
        "score": 0.72,
        "spontaneous": false
      }
    }
  ],
  "dialogue_history": {
    "turns_used": 4,
    "turns_available": 8
  },
  "aiim": {
    "emotion": "warm",
    "emotion_src": "visitor_engaged",
    "active_intentions": ["seek_connection"],
    "aspects_changed": {"se": 0.73, "pe": 0.42}
  },
  "subconscious_signal": null
}
```

### Откуда брать данные для /api/prompt/current

Нужно расширить `trace_record` в Orchestrator.py (строка 3509):

```python
trace_record = {
    ...existing fields...,
    # НОВЫЕ ПОЛЯ:
    "identity_block": identity_block,           # уже есть в локальной переменной
    "ctx_weather": weather_ctx,                 # уже есть в локальной переменной
    "echo_hint_text": echo_hint,               # уже есть в локальной переменной
    "ctx_body": ctx_body if tuning.diagnostics.trace_prompts else None,  # весь второй system msg
    "aiim_snapshot": {                          # snapshot AIIM state
        "emotion": aiim_state.emotion if aiim_state else None,
        "emotion_src": aiim_state.emotion_src if aiim_state else None,
        "intentions": aiim_state.intentions.active_names() if aiim_state else [],
    },
}
```

**Альтернатива (без изменения trace_record):** отдельный `current_turn_state` dict в runtime_state, обновляемый каждый turn и читаемый /api/prompt/current напрямую.

### Endpoint реализация

```python
@app.get("/api/prompt/current")
async def get_prompt_current() -> dict:
    """Последний turn с разбивкой промпта по секциям.
    
    Не требует trace_prompts=True — секции строятся из trace_record полей.
    Persona text доступна только при trace_prompts=True (защита объёма).
    """
    items = list(prompt_trace)
    if not items:
        raise HTTPException(status_code=404, detail="no_turns_yet")
    last = items[-1]
    
    # Строим sections из уже сохранённых полей
    sections = _build_prompt_sections(last)
    
    return {
        "turn_id": last.get("turn_id"),
        "ts": last.get("ts"),
        "transcript": last.get("transcript"),
        "reply": last.get("reply"),
        "total_chars": last.get("prompt_chars", 0),
        "trace_prompts_enabled": tuning_store.current().diagnostics.trace_prompts,
        "sections": sections,
        "dialogue_history": {
            "turns_used": last.get("history_turns_used", 0),
        },
        "aiim": last.get("aiim_snapshot"),
        "subconscious_signal": runtime_state.get("last_subconscious_signal"),  # Phase 36
    }
```

---

## 7. Prompt Viewer UI Component

### Цветовая схема секций

| Секция | CSS переменная | Цвет (dark theme) |
|--------|---------------|------------------|
| `persona` | `--section-persona` | #1a3a5c (тёмно-синий) |
| `ctx.identity` | `--section-identity` | #3a1a5c (фиолетовый) — AIIM |
| `ctx.memory` | `--section-memory` | #1a4a2c (тёмно-зелёный) |
| `ctx.recent_visitors` | `--section-recent` | #3a3a1a (тёмно-жёлтый) |
| `ctx.vision` | `--section-vision` | #1a3a1a (зелёный) — VLM |
| `ctx.sensors` | `--section-sensors` | #1a2a3a (серо-синий) |
| `ctx.weather` | `--section-weather` | #2a3a4a (серый) — редко |
| `hint` (echoes) | `--section-echo` | #4a3a1a (янтарный) |
| `hint` (chinese) | `--section-chinese` | #4a2a1a (оранжево-красный) |
| `subconscious` | `--section-subconscious` | #3a0a5c (насыщенный фиолетовый) |

### HTML структура компонента (промт-блок)

```html
<div class="prompt-viewer">
  <!-- Заголовок с метаданными -->
  <div class="prompt-meta card">
    <span class="ts">14:32:10</span>
    <span class="source badge">voice</span>
    <span class="chars">2847 ch</span>
    <span class="sections-count">7 блоков</span>
    <button class="expand-all">Развернуть всё</button>
  </div>

  <!-- Transcript → Reply -->
  <div class="card prompt-exchange">
    <div class="transcript">👤 Адам, ты меня слышишь?</div>
    <div class="reply">→ Слышу. Ты здесь, и я тебя замечаю.</div>
  </div>

  <!-- Sections (collapsible) -->
  <div class="section section-identity expanded">
    <div class="section-header" onclick="toggle()">
      <span class="section-tag">[ctx.identity]</span>
      <span class="section-label">AIIM Identity State</span>
      <span class="section-chars">44 ch</span>
      <span class="chevron">▼</span>
    </div>
    <div class="section-body mono">
      emotion=warm|src=visitor_engaged
      se=0.73↑
      intention=seek_connection
    </div>
  </div>

  <div class="section section-vision collapsed">
    <div class="section-header" onclick="toggle()">
      <span class="section-tag">[ctx.vision]</span>
      <span class="section-label">Visual Context (VLM)</span>
      <span class="section-chars">56 ch</span>
      <span class="chevron">▶</span>
    </div>
    <div class="section-body hidden">...</div>
  </div>

  <!-- Hint badge (если есть) -->
  <div class="section section-echo">
    <div class="section-header">
      <span class="section-tag">[hint]</span>
      <span class="section-label">Echo: echo_theseus_01</span>
      <span class="badge">score 0.72</span>
    </div>
    <div class="section-body mono">
      Помни о корабле Тесея — каждая деталь заменяется...
    </div>
  </div>
</div>
```

### UX правила

1. **По умолчанию** — `[ctx.identity]` и `[hint]` раскрыты (самое важное), остальные свёрнуты
2. **[ctx.weather]** — не показывать если `available=false`
3. **persona** — показывать только заголовок с chars, если `trace_prompts_enabled=false` (сообщение: "Enable in Tuning → diagnostics → trace_prompts to see full persona")
4. **Авто-обновление** — раз в 5 секунд (не 30 как в prompts.js)
5. **Субъекты SubconsciousSignal** — отдельный блок под [ctx.identity], показывается только при Phase 36 (когда runtime_state содержит last_subconscious_signal)

---

## 8. Изменения для реализации

### Backend (минимальные)

**1. Расширить trace_record** (Orchestrator.py ~3509):
```python
# Добавить в trace_record:
"identity_block": identity_block,
"weather_ctx": weather_ctx or "",
"echo_hint_text": echo_hint or "",
```

**2. Добавить GET /api/prompt/current** (Orchestrator.py после строки 2928):
```python
@app.get("/api/prompt/current")
async def get_prompt_current() -> dict[str, Any]:
    # reads from prompt_trace[-1]
    # builds sections from known fields
    # returns structured JSON per schema above
```

### Frontend

**Вариант A: новая панель `promptCurrent.js`** — отдельный файл для "live view" текущего состояния промпта, монтируется на вкладку рядом с prompts.js.

**Вариант B: расширить prompts.js** — заменить raw text viewer в buildDetailContent() на секционированное дерево с цветовыми блоками.

Рекомендую **Вариант A** — prompts.js уже работает и обратно совместим, новый endpoint чище.

---

## 9. Что такое "блок системного промпта и инъекций подсознания" в UI

Исходя из анализа:

**"Системный промпт"** в контексте UI = **два компонента вместе**:
1. `messages[0]` (persona) — статичный, меняется только при правке файлов персоны
2. `messages[1]` (ctx_body) — динамический, меняется каждый turn

**"Инъекции подсознания"** = три уровня:
- `[ctx.identity]` — AIIM dynamic state (эмоция, намерения, aspect vector)
- `[hint]` — Echo/Chinese gate (подсознательный hint к LLM о том, что "всплыло из памяти")
- Future `SubconsciousSignal` (Phase 36) — не в промпте, а premod к AIIM state

В UI это должен быть единый "PROMPT & INJECTIONS" блок:

```
┌──────────────────────────────────────────────────┐
│ PROMPT & INJECTIONS  turn 14:32:10  2847 ch  ▼   │
├──────────────────────────────────────────────────┤
│ [PERSONA]       1840 ch  ▶ (свёрнуто)            │ синий
│ ─────────────────────────────────────────────    │
│ [ctx.identity]   44 ch   ▼                        │ фиолетовый
│   emotion=warm|src=visitor_engaged                │
│   se=0.73↑, intention=seek_connection             │
│ ─────────────────────────────────────────────    │
│ [ctx.vision]    56 ch   ▶ (свёрнуто)             │ зелёный
│ [ctx.sensors]   20 ch   ▶                        │ серо-синий
│ [ctx.memory]   312 ch   ▶                        │ тёмно-зелёный
│ ─────────────────────────────────────────────    │
│ [hint: echo_theseus_01]  score=0.72  ▼           │ янтарный
│   "Помни о корабле Тесея..."                      │
│ ─────────────────────────────────────────────    │
│ history: 4 turns                                  │
└──────────────────────────────────────────────────┘
```

---

## 10. Зазоры между текущим и желаемым

| Что нужно | Текущее состояние | Что добавить |
|-----------|------------------|-------------|
| ctx_body в trace | НЕТ — не сохраняется | +3 поля в trace_record |
| /api/prompt/current | НЕТ | Новый endpoint |
| Секционированный viewer | prompts.js показывает raw text | Новый компонент promptCurrent.js |
| SubconsciousSignal в trace | НЕТ (Phase 36 not yet) | После Phase 36: runtime_state["last_subconscious_signal"] |
| identity_block в trace | НЕТ — вычисляется но не сохраняется | +1 поле в trace_record |

**Минимальный diff для работающего viewer:**
- 3 строки в trace_record (~строка 3521)
- ~50 строк нового endpoint в Orchestrator.py
- ~150 строк promptCurrent.js

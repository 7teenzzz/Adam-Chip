# UI Live Widgets — Research
**Date:** 2026-06-11
**Branch:** ultimate-integration-v2 / subconscious-symbiont context
**Phase:** Pre-Phase 36 (SubconsciousProcessor) UI preparation

---

## 1. Что сейчас есть на главной chat-странице

### Структура chat.js (`mount()`)

Страница chat — это единственная карточка `.card` с двух-колоночным `grid-template-columns: 3fr 2fr`.

**Левая колонка (3fr) — диалог:**
- `#chat-transcript` — лента пузырей (viewer/adam), стрим через SSE `llm_partial` + финал `adam_reply`
- `textarea` — ручной ввод текста
- Кнопки: Отправить, ⏹ стоп (interrupt), Очистить

**Правая колонка (2fr) — vision + voice:**
- Метка источника камеры + время снимка
- `<img>` — JPEG-снимок камеры (polling каждые 1.5с через `/api/camera/snapshot.jpg`)
- `sceneCaption` — текст `scene_cache.text` (VLM описание сцены), обновляется через `scene_updated` SSE
- "Микрофон · OWW" + `micSourceBadge` (ESP32 stereo/mono/local)
- `eqCanvas` (WakeMeter, 24-полосный FFT-эквалайзер) + `vuCanvas` (VU-метр L/R)
- Статус-dot (`hearingDot`) + `asrBox` — текущее состояние pipeline: ожидаю/слушаю/думаю/говорю
- `countdownTrack` — прогресс-бар таймаута ожидания

**Боковая панель (side, всегда видна):**
- `side-latency` — LLM/TTS/ASR/VLM задержки из `/api/agent/status`
- `side-events` — стрим последних 80 событий из SSE (отфильтрованные, список в `SIDE_EVENTS`)

---

## 2. SSE события — формат и механика

### Транспорт

Единственный SSE-стрим: `GET /api/agent/stream` (EventSource).
Формат каждого сообщения:
```
id: <uuid>
data: {"id": "...", "ts": "2026-06-11T...", "type": "...", "payload": {...}, "turn_id": "..."}
```

Подписка в `api.js` (`subscribeEvents`): EventSource с авто-реконнектом + экспоненциальный backoff 500ms → 8s.

В `main.js`:
```js
subscribeEvents((event) => {
  appendEventToSide(event);         // фильтр SIDE_EVENTS
  state.patch("last_events", { last: event });   // все компоненты читают через state
  // режим-refresh на отдельных типах
});
```

Компоненты подписываются через `state.subscribe("last_events", callback)`.

### Актуальные типы событий (задокументированные в SIDE_EVENTS + chat.js)

**Pipeline:**
| Событие | Payload (ключи) |
|---------|----------------|
| `wake_word_detected` | `score`, `silence_timeout_sec` |
| `asr_partial` | `state` ("speech_started"), `level`, `utterance_id` |
| `asr_final` | `text`, `source`, `asr_ms` |
| `asr_wake_only` | `raw`, `reason` |
| `llm_thinking_started` | — |
| `llm_thinking_finished` | — |
| `llm_partial` | `text`, `index` |
| `tts_started` | — |
| `tts_finished` | — |
| `adam_reply` | `text`, `source`, `voice_degraded`, `tts`, `action`, `mcu`, `timings` |
| `viewer_transcript` | `text`, `source`, `sensors`, `visitor_name`, `echo` |

**Аудио (высокочастотные):**
| Событие | Payload |
|---------|---------|
| `audio_level` | `level`, `level_l`, `level_r`, `channels`, `source`, `bands[]` |

**Scene / VLM:**
| Событие | Payload |
|---------|---------|
| `scene_updated` | `text`, `stale` |
| `scene_engagement_changed` | `from`, `to` |
| `vlm_request_started` | `frame_bytes`, `camera_source` |
| `vlm_request_failed` | `error` |

**AIIM (текущие):**
| Событие | Payload |
|---------|---------|
| `aiim_humor_reaction` | `reaction` ("positive"/"negative"), `turn` |
| `aiim_turn_error` | `error` |
| `aiim_drift_error` | `error` |
| `aiim_init_error` | `error` |

**Системные:**
| Событие | Payload |
|---------|---------|
| `voice_state_change` | `from`, `to` |
| `mode_changed` | `mode` |
| `prompt_trace` | `ts`, `source`, `transcript_len`, `prompt_chars`, `echo`, `semantic_used` |

**КРИТИЧНО:** Текущая AIIM-логика **НЕ эмитирует событие с текущей эмоцией**. После каждого turn в `Orchestrator.py` (~line 3445–3476) эмоция вычисляется и сохраняется в `session_state["aiim_state"]`, но в event_log попадает **только** `aiim_humor_reaction` (при изменении через реакцию на юмор). Нет события `aiim_emotion_changed` или `aiim_state_snapshot`.

---

## 3. Как live-виджеты подключаются к SSE — паттерн

Пример: chat.js — `scene_updated` обновляет `sceneCaption`.

```js
// В mount():
const unsubscribe = state.subscribe("last_events", (payload) => {
  const ev = payload.last;
  if (!ev) return;

  if (ev.type === "scene_updated") {
    sceneCaption.textContent = ev.payload.text + (ev.payload.stale ? " (устарело)" : "");
  }
  // ... другие типы
});

// В возврате из mount() — teardown:
return () => {
  unsubscribe();
  // ... освободить таймеры
};
```

Второй паттерн — polling через `api.get()` + `state.subscribe("status", ...)` для медленно меняющихся данных (latency, mode).

Третий паттерн — отдельный `api.get()` при mount без подписки на SSE (например, persona.js, prompts.js).

---

## 4. Существующие AIIM endpoint'ы и данные

### В `/api/agent/status` — AIIM данных НЕТ

Структура status (`_status_payload()`) содержит только:
- `agent.mode`, `agent.speaking`, `agent.thinking`, `agent.latency_ms.*`
- `voice_loop.status()` (включает `voice_state`, `mic_active_source`, etc.)
- `scene_cache.text`, `scene_cache.stale`

AIIM state (`session_state["aiim_state"]`) в status **не включён**.

### Нужен новый endpoint: `/api/agent/aiim` или расширение status

Для EmotionWidget нужно либо:
1. Добавить `aiim` ключ в `_status_payload()` — и UI читает через polling 4с
2. Добавить SSE событие `aiim_state_snapshot` после каждого turn — мгновенное обновление

### Что доступно через polling уже сейчас

`/api/agent/events?types=aiim_humor_reaction` — последние события реакций на юмор.
`/api/agent/turns` — полный turn с metadata, но без AIIM состояния.

---

## 5. Что такое Task B (SubconsciousSignal) — статус на 2026-06-11

Task B — **запланированная** фича Phase 36 (SubconsciousProcessor), **НЕ реализована**.

Это второй запрос к Cosmos Reason2-2B после каждого `asr_final`:
- Input: scene description (Task A) + transcript + acoustic features
- Output JSON: `{emotion_hint, flora_mode, intensity, reasoning}`

Планируемое SSE-событие: `subconscious_signal_generated` с payload:
```json
{
  "emotion_hint": "curious",
  "flora_mode": "attentive",
  "intensity": 0.7,
  "reasoning": "Visitor leaning in with clear question."
}
```

Планируемый новый модуль: `System/adam/subconscious.py` (класс `SubconsciousAnalyzer`).

---

## 6. Проект компонентов

### 6.1 EmotionWidget

**Назначение:** живой индикатор текущей эмоции Адама (из AIIM).

**Данные источник:**
- Сейчас: нет SSE-события. Нужно добавить `aiim_state_snapshot` в event_log.append() после строки 3474 в Orchestrator.py:
  ```python
  event_log.append("aiim_state_snapshot", {
      "emotion": aiim_state.emotion,
      "emotion_src": aiim_state.emotion_src,
      "turn": aiim_state.turn,
      "intentions": aiim_state.intentions.active_names(),
  }, turn_id=turn_id)
  ```
- Или: добавить `aiim` секцию в `_status_payload()` (polling, но без lag).

**5 состояний эмоции → цвет/иконка:**
| Эмоция | Цвет | Иконка |
|--------|------|--------|
| `curious` | `var(--accent)` зелёный | 🔍 |
| `warm` | `#f59e0b` янтарный | ✨ |
| `unease` | `#8b5cf6` фиолетовый | ⚡ |
| `sharp` | `#22d3ee` циан | ⚔ |
| `calm` | `#64748b` серый | 🌊 |

**Размещение на странице:**
Лучшее место — в правой колонке chat-панели, **между** sceneCaption и блоком "Микрофон · OWW". Это natural position для "состояния Адама" в контексте воспринимаемой сцены.

Альтернатива: в topbar рядом с индикаторами сервисов (компактный вариант: цветная точка + emoji эмоции).

**Структура виджета:**
```js
// Compact version: dot + label + src
el("div", { style: "display:flex; align-items:center; gap:8px" }, [
  el("span", { id: "emotion-dot", style: "width:10px; height:10px; border-radius:50%; background:..." }),
  el("span", { id: "emotion-label", class: "caps", style: "font-size:11px" }, "ЛЮБОПЫТСТВО"),
  el("span", { id: "emotion-src", class: "dim", style: "font-size:10px" }, "decay"),  // emotion_src
])
```

**Подписка:**
```js
state.subscribe("last_events", (payload) => {
  const ev = payload.last;
  if (ev.type === "aiim_state_snapshot") {
    updateEmotionWidget(ev.payload.emotion, ev.payload.emotion_src);
  }
});
```

---

### 6.2 SubconsciousResponsesFeed

**Назначение:** блок с последними 5–10 Task B outputs.

**ВАЖНО:** Task B (Phase 36) ещё не реализован. Виджет нужно строить под будущее событие `subconscious_signal_generated`.

**Данные источник:**
- SSE: `subconscious_signal_generated` payload = `{emotion_hint, flora_mode, intensity, reasoning}`
- Polling fallback: `/api/agent/events?types=subconscious_signal_generated&limit=10`

**Структура виджета (feed):**
```js
// Каждая запись:
el("div", { class: "fade-in", style: "border-bottom: 1px solid var(--bg-3); padding: 6px 0; font-size:11px" }, [
  el("span", { class: "dim" }, ts),
  el("span", { style: `color: ${EMOTION_COLORS[emotion_hint]}` }, emotion_hint),
  el("span", { class: "caps dim" }, " → " + flora_mode),
  el("div", { class: "muted", style: "font-size:10px; margin-top:2px" }, reasoning),
  // intensity bar
  el("div", { style: `width: ${intensity*100}%; height:2px; background:var(--accent); border-radius:1px` }),
])
```

**Обновление:** через SSE (`state.subscribe("last_events")`), хранить ring-buffer 10 записей в локальной переменной.

**Размещение:**
- Отдельная секция на chat-странице (под правой колонкой, full width)
- Или как отдельный коллапсируемый блок ниже диалога (т.к. данных пока нет)
- Рекомендация: добавить в правую колонку как раскрывающийся раздел "Подсознание"

---

### 6.3 PromptInjections — виджет инжекций в системный промпт

**Назначение:** показывать что сейчас инжектируется в системный промпт: [ctx.identity], [ctx.vision], [ctx.memory], [ctx.weather], эхо.

**Данные источник:**
- SSE: `prompt_trace` (уже эмитируется) — payload содержит: `echo` (метаданные инжекции эхо), `semantic_used`, `prompt_chars`
- НО: полный `system_prompt` эмитируется только при `tuning.diagnostics.trace_prompts = true`
- Partial данные всегда доступны: echo metadata, semantic_used, visitor_name, scene

**Альтернатива для полного контента:** endpoint `/api/prompts` (panel prompts.js уже существует)

**Структура виджета (compact badges):**
```js
// Бейджи активных инжекций:
[ctx.vision]  ✓  // если scene_cache.text не пустой
[ctx.memory]  ✓  // если semantic_used
[ctx.weather] ✓  // если weather_ctx
[ctx.identity] emotion=unease  // если identity_block не пустой (через aiim_state_snapshot)
echo: "Я видел этот свет раньше..." (pool: echoes, id: 3)
```

**Данные берём из:**
- `scene_cache` → из `/api/agent/status` (polling)
- `prompt_trace` SSE → `semantic_used`, `echo`
- `aiim_state_snapshot` SSE → `identity_block` активность (если эмоция != "curious" + нет intentions → блок пустой)

---

## 7. Необходимые серверные изменения

### Минимальный набор (для EmotionWidget)

**Добавить в `Orchestrator.py` после строки ~3474:**
```python
# После aiim_state.record_turn() и aiim_state.turn += 1
event_log.append("aiim_state_snapshot", {
    "emotion": aiim_state.emotion,
    "emotion_src": aiim_state.emotion_src,
    "turn": aiim_state.turn,
    "intentions": aiim_state.intentions.active_names(),
    "identity_block_active": bool(identity_block.strip()),
}, turn_id=turn_id)
```

Это единственное изменение для EmotionWidget — одна строка в Orchestrator.py.

### Для SubconsciousResponsesFeed (Phase 36)

При реализации Task B добавить в `subconscious.py`:
```python
event_log.append("subconscious_signal_generated", {
    "emotion_hint": signal.emotion_hint,
    "flora_mode": signal.flora_mode,
    "intensity": signal.intensity,
    "reasoning": signal.reasoning,
}, turn_id=turn_id)
```

### Для status polling (опционально)

Добавить `aiim` секцию в `_status_payload()`:
```python
aiim_st = session_state.get("aiim_state")
"aiim": {
    "emotion": aiim_st.emotion if aiim_st else None,
    "emotion_src": aiim_st.emotion_src if aiim_st else "",
    "turn": aiim_st.turn if aiim_st else 0,
    "enabled": bool(tuning.identity.enabled),
} if aiim_st else None,
```

---

## 8. Место размещения на chat-странице

Предлагаемая структура правой колонки после добавления виджетов:

```
[camera label + timestamp]
[camera image]
[VLM scene caption]
━━━━━━━━━━━━━━━━━━━━━
[AIIM EmotionWidget]         ← НОВЫЙ (1 строка: dot + emotion + src)
━━━━━━━━━━━━━━━━━━━━━
[Prompt injections badges]   ← НОВЫЙ (бейджи активных ctx-блоков)
━━━━━━━━━━━━━━━━━━━━━
[Микрофон · OWW]
[EQ canvas + VU meter]
[hearing dot + asrBox]
[countdown bar]
```

Высота правой колонки сейчас ~500px. EmotionWidget займёт ~28px, prompt badges ~40px — суммарно +68px, что укладывается в `overflow-y: auto`.

**Subconscious feed** — отдельная секция ниже основной карточки, в `target.appendChild(secondCard)`. Это меньше загромождает chat и согласуется с Phase 36 (когда функционал появится).

---

## 9. Паттерн реализации (итог)

```js
// В chat.js mount():

// --- EmotionWidget ---
let currentEmotion = null;
const emotionDot = el("span", { style: "width:10px; height:10px; border-radius:50%; background:var(--dim); flex-shrink:0" });
const emotionLabel = el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "—");
const emotionSrc   = el("span", { class: "dim", style: "font-size:10px" }, "");

function updateEmotion(emotion, src) {
  const COLORS = {
    curious: "var(--accent)", warm: "#f59e0b", unease: "#8b5cf6",
    sharp: "#22d3ee", calm: "#64748b"
  };
  const LABELS = {
    curious: "ЛЮБОПЫТСТВО", warm: "ТЕПЛО", unease: "ТРЕВОГА",
    sharp: "ОСТРОТА", calm: "ПОКОЙ"
  };
  currentEmotion = emotion;
  emotionDot.style.background = COLORS[emotion] || "var(--dim)";
  emotionLabel.textContent = LABELS[emotion] || emotion || "—";
  emotionSrc.textContent = src ? `· ${src}` : "";
}

// --- В SSE subscribe (state.subscribe "last_events"): ---
if (ev.type === "aiim_state_snapshot") {
  updateEmotion(ev.payload.emotion, ev.payload.emotion_src);
}

// --- Инициализация из status polling: ---
state.subscribe("status", () => {
  const aiim = state.get("status")?.aiim;
  if (aiim?.emotion && aiim.emotion !== currentEmotion) {
    updateEmotion(aiim.emotion, aiim.emotion_src);
  }
});
```

---

## 10. Итоговая таблица: что нужно сделать

| Компонент | Backend изменение | Frontend изменение | Зависимость |
|-----------|-------------------|-------------------|-------------|
| EmotionWidget | `aiim_state_snapshot` event в Orchestrator.py (~5 строк) | EmotionWidget в chat.js правой колонке | Нет |
| EmotionWidget polling | `aiim` в `_status_payload()` (~8 строк) | `state.subscribe("status")` | Нет |
| SubconsciousResponsesFeed | Phase 36 (`subconscious_signal_generated` event) | Feed компонент в chat.js | Phase 36 |
| PromptInjectionsBadges | Нет (данные уже в `prompt_trace` + `status`) | Badges компонент из существующих данных | Нет |

**Минимально жизнеспособная реализация (без Phase 36):**
1. `aiim_state_snapshot` event → EmotionWidget
2. Prompt injection badges из `prompt_trace` SSE + `scene_cache` polling
3. SubconsciousResponsesFeed — placeholder "данные появятся в Phase 36"

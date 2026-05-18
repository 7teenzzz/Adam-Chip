---
title: UI: убрать локальные дефолты, читать pipeline state из snapshot
date: 2026-05-16
priority: MEDIUM
context: [voice-pipeline-vs-ui-layering](../../notes/voice-pipeline-vs-ui-layering.md)
---

# UI: pipeline state как single source of truth

## Проблема

`chat.js` хранит локальные переменные дублирующие pipeline state:
- `hearingState = "loading"` ([chat.js:195](../../../System/WebUI/static/js/panels/chat.js#L195)) → label «🎧 Инициализация»
- `micSource = "local"` ([chat.js:107](../../../System/WebUI/static/js/panels/chat.js#L107))

При remount панели (навигация Чат → Настройки → Чат) значения пересоздаются с фиктивными дефолтами. SSE-события `voice_loop_started` и `audio_level` уже отзвучали — UI ждёт следующих, отображая ложь.

## Fix

### 1. `chat.js`: читать pipeline state из `/api/agent/status` на mount

```js
// БЫЛО (chat.js:107, 195):
let micSource = "local";
let hearingState = "loading";

// СТАЛО:
const initialStatus = state.get("status");
const vl = initialStatus?.voice_loop;
let micSource = vl?.mic_active_source || null;  // null = ещё не знаем
let hearingState = vl?.running ? "standby" : "unknown";
```

### 2. Добавить `"unknown"` state в HEARING_LABELS

```js
const HEARING_LABELS = {
  unknown:      "—",  // pre-snapshot, серый
  loading:      "🎧 Инициализация",   // pipeline mention, но running=false
  standby:      "🎧 Ожидаю обращения",
  ...
};
```

«Инициализация» оставить ТОЛЬКО для случая «status загружен, voice_loop.running=false» — то есть когда pipeline реально мёртв. До загрузки snapshot — `unknown` (нейтральный лейбл).

### 3. Mic badge: тот же подход

```js
function vuColorTriplet() {
  if (micSource === null) {
    return { rgb: "150,150,160", emoji: "○", label: "—" };
  }
  // ... остальное
}
```

### 4. Re-fetch status при mount если устарел

```js
// В mount():
const lastFetch = state.get("status_fetched_at") || 0;
if (Date.now() - lastFetch > 2000) {
  refreshStatus();  // expose from main.js
}
```

## Acceptance

- ✅ Открыть Чат на свежем оркестраторе (voice_loop running) → сразу `Ожидаю обращения`, mic badge показывает `ESP32 stereo`/`ESP32 mono` без задержки
- ✅ Навигация Чат → Настройки → Чат → state остаётся прежним, нет вспышки «Инициализация»
- ✅ Только при реально мёртвом voice_loop (после фикса fix-vad-loop этого не должно быть) — показ `Инициализация`

## Затронутые файлы

- `System/WebUI/static/js/panels/chat.js` — ~30 строк
- `System/WebUI/static/js/main.js` — экспортировать `refreshStatus`

## Связано

- Зависит от [fix-vad-loop-exception-handling](fix-vad-loop-exception-handling.md) косвенно — без него pipeline и правда умирает, и UI правильно это показывает.
- Та же логика нужна для других панелей (settings, services) — пометить в todo на будущее.

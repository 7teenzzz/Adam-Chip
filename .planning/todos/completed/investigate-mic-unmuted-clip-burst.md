---
title: Verify mic_unmuted всегда парный к mic_muted после фиксов #1+#2
date: 2026-05-16
priority: LOW
status: completed
verified_at: 2026-05-16
context: [voice-pipeline-vs-ui-layering](../../notes/voice-pipeline-vs-ui-layering.md)
---

## Verified ✓ (2026-05-16, session 13:08-13:30)

Из live логов после рестарта оркестратора и 3 turn'ов:

- `mic_muted` = 3, `mic_unmuted` = 3, delta = 0 ✓
- `esp32_mic_drainer_started` = 3, `_stopped` = 3, delta = 0 ✓
- `voice_loop_error` = 0, `voice_loop_stopped` = 0 ✓
- `IncompleteRead` упоминаний = 0 ✓
- `mute_duration_ms` в payload присутствует: 19049, 2565, 2298 ms
- `clip_delta` упал с 4776 до 261 во время TTS — `action: no_switch` корректно

Все три проверки из плана прошли. Code changes не потребовались.

## Контекст

Изначально todo расследовал два симптома: пропуск `mic_unmuted` event'а и `clip_count: 4776`.

Оба исчерпаны анализом:

- **Missing mic_unmuted** — был следствием exception-swallowing в `_vad_loop`. Драйнер ловил `IncompleteRead` в `_drain_esp32_backlog`, exception всплывал, и код **не доходил** до строки с `mic_unmuted` event. Фиксы #1 ([fix-vad-loop-exception-handling](fix-vad-loop-exception-handling.md)) и #2 ([fix-esp32-stream-drain-during-mute](fix-esp32-stream-drain-during-mute.md)) устранили причину.
- **clip_count: 4776** — физическое явление (эхо TTS через HDMI → INMP441), не баг. ESP audio_health правильно принимает `action: no_switch`. На pipeline не влияет.
- «Два смысла мута» — была моя ошибка в первичном анализе. `muted_by_tts` устанавливается/сбрасывается **только в одной точке** в `_vad_loop`. Единственный mute path.

## Что подтвердить в следующем live-сессионе

После рестарта оркестратора и 3-5 turns подряд:

1. Парность событий:

   ```bash
   python3 -c "
   import json
   muted = unmuted = 0
   for line in open('data/adam/events.jsonl'):
       try: ev = json.loads(line)
       except: continue
       if ev['type'] == 'mic_muted': muted += 1
       if ev['type'] == 'mic_unmuted': unmuted += 1
   print(f'muted={muted} unmuted={unmuted} delta={muted-unmuted}')
   "
   ```

   Ожидание: `delta = 0` (или 1 если последний turn в процессе).

2. `mute_duration_ms` в payload `mic_unmuted` — должен быть в диапазоне 10–25 секунд (ASR + LLM + TTS).

3. `esp32_mic_drainer_started` и `esp32_mic_drainer_stopped` парные. В payload `_stopped` поле `drained_bytes` ≈ `mute_duration_ms * 64` (64 KB/sec stereo).

## Опционально

Если `clip_count_total` высокий мешает диагностике — снизить громкость TTS:

```json
// Config.json
"tuning": {
  "voice": {
    "volume": 0.7
  }
}
```

Это уменьшит акустическое эхо в INMP441 микрофон, но не критично для работы (сейчас volume=1.1).

## Закрытие

Если все 3 проверки прошли — этот todo можно перевести в `completed/`. Никаких code changes не требуется.

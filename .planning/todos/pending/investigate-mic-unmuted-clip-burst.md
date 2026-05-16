---
title: Investigate: mic_unmuted не срабатывает после tts_finished, clip_burst 4776
date: 2026-05-16
priority: LOW
context: [voice-pipeline-vs-ui-layering](../../notes/voice-pipeline-vs-ui-layering.md)
---

# Investigate mic_unmuted + clip_burst во время TTS

## Симптом из лога

```
11:57:04 mic_muted              reason=asr_transcribing
11:57:13 asr_final
11:57:16 tts_started
11:57:23 tts_finished
11:57:24 esp32_audio_health     clip_count_total=4776 clip_delta=4776
```

В логе **нет события `mic_unmuted`** между `mic_muted` и моментом `voice_loop_stopped`. Микрофон оставался замью́ченным во время TTS, при этом ESP32 audio health фиксирует **4776 клипящих фреймов** за единичный poll-интервал (60 сек) — катастрофически много.

## Гипотезы

### 1. mic_muted имеет два смысла

- **`muted_by_tts`** ([Orchestrator.py:352](../../../System/Orchestrator.py#L352)) — флаг полу-дуплексного режима, выставляется в True перед ASR transcribing
- **`asr_transcribing` mute** ([Orchestrator.py:1072](../../../System/Orchestrator.py#L1072)) — логический мут для VAD, чтобы не накапливать речь во время transcribe

`mic_unmuted` события сейчас эмитятся только из одной точки ([:1095](../../../System/Orchestrator.py#L1095)) — после `_drain_esp32_backlog`. Если drain бросил exception (как в случае IncompleteRead) → unmute event пропущен.

### 2. TTS-сторонний mute

Возможно есть отдельный mute path на время TTS playback (через TTS client?) который не логирует unmute. Найти все места где меняется `muted_by_tts`.

### 3. clip_burst 4776 — эхо TTS

`half_duplex_mute=True` декларирует что mic должен быть заглушен. Но клиппинг 4776 фреймов = ~95 сек клиппа за 60-секундное окно — нереально. Возможные источники:
- TTS звук с HDMI динамика → INMP441 микрофон ESP32 (реверберация в комнате)
- Электрические наводки на ESP при работе спикера (PAM8403 рядом)
- Самовозбуждение ESP при перегруженной шине I2S после длительной паузы чтения

## Что проверить

1. `grep -n "muted_by_tts" System/Orchestrator.py` — найти все точки присваивания
2. В реальном run-логе сравнить `tts_started`/`tts_finished` с `mic_muted`/`mic_unmuted` — должны быть в паре
3. Проверить ESP32 firmware: что делает `/audio` endpoint при отсутствии чтения? Drop'ит ли клиента? Какой watchdog?
4. Прогнать turn БЕЗ TTS playback (например через `output_target=esp32_speaker` с заглушкой) — будут ли clip events?

## Связано

- После [fix-esp32-stream-drain-during-mute](fix-esp32-stream-drain-during-mute.md) ESP не будет накапливать buffer → возможно clip_burst исчезнет.
- Реальный TTS-mute и его восстановление — отдельный архитектурный момент, не блокирует основной flow.

## Приоритет LOW потому что

Pipeline жизненно не зависит от этого фикса. ESP audio_health и так не делает auto-switch при clip_burst (`action: no_switch`). Косметика логов и точность диагностики.

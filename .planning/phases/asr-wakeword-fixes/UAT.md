---
status: testing
phase: asr-wakeword-fixes
source: git diff HEAD~3 (Config.json, Orchestrator.py, ASR_Whisper.py, wake_word.py, inference.py)
started: 2026-05-11T20:00:00Z
updated: 2026-05-11T20:15:00Z
---

## Current Test

number: 1
name: Cold Start ASR Warmup
expected: |
  После перезапуска оркестратора в events.jsonl появляется warmup_asr {ok: true}
  до первого голосового turn'а. Первый turn: asr_ms < 4000ms (было 8–22s).
awaiting: user response

## Tests

### 1. Cold Start ASR Warmup
expected: После перезапуска оркестратора warmup_asr{ok:true} в events.jsonl. Первый turn: asr_ms < 4000ms.
result: [pending]

### 2. Wake-word-only utterance — empty guard
expected: Произнести только «адам». В events.jsonl — asr_wake_only. НЕ появляется viewer_transcript и adam_reply.
result: [pending]

### 3. Strip wake word from LLM transcript
expected: «Адам, как дела?» → asr_final.raw содержит «адам», viewer_transcript.text — только «как дела?».
result: pass
notes: авто-проверен регексом. 6 сценариев (только wake word, начало, середина, «адама» как часть слова, дохлый). Все OK. Empty guard работает.

### 4. Post-TTS cooldown 1.5s
expected: После tts_finished wake_word_detected не появляется 1.5с. Нет ложных turn'ов от эха TTS.
result: [pending]

### 5. Command endpointing 1.2s
expected: После команды (после wake word) ASR запускается через ~1.2с тишины, не 2с. Субъективно быстрее.
result: [pending]

### 6. OpenWakeWord engine в событии
expected: wake_word_detected.engine = "openwakeword". Fallback (Whisper regex) не используется.
result: [pending]

### 7. no_speech_prob filter
expected: При provider=whisper галлюцинации на шум отфильтрованы. При provider=speaches — skip (Docker VAD).
result: skipped
reason: provider=speaches активен. Фильтр no_speech_prob в ASR_Whisper.py корректно добавлен (авто-проверено), но при speaches он не задействован — speaches использует свой внутренний VAD.

### 8. Wake word scripts executable
expected: adam_record_wakeword.sh и adam_train_wakeword.sh существуют с флагом +x.
result: pass
notes: авто-проверено. Оба файла rwxrwxr-x, 6297 и 9369 байт.

## Summary

total: 8
passed: 2
issues: 0
pending: 5
skipped: 1
blocked: 0

## Gaps

[none yet]

# Interaction Model — Главы 3.2.5, 3.2.6, 3.3.4

## Перцептивный контур (3.2.5)

### Audio input chain
1. **VAD** — voice activity detection, отсекает тишину/шум, определяет границу события.
2. **ASR.py** — преобразует речевой фрагмент в текст.
3. **Контекстные метки** (опционально) — эмоциональная окраска, прерывистость, агрессия.

### Visual input chain
- **Камера** + датчики.
- **VILA1.5-3B в NanoБЯЗ контейнере** — быстрое описание сцены, передаётся в orchestrator.
- **Условный вызов** — не каждый цикл; при долгом отсутствии речи, смене сцены, проактивном сканировании.

---

## Командный контур (3.2.6)

**Принцип уплотнения смысла:**

```text
LLM full response
  ↓ Commander.py (постобработка)
Short markers: [радость], [удивление], [грусть], [настороженность]
  ↓ Communication.py
MCU packet
  ↓ ESP32-S3 firmware
Light + Sound + Vibration patterns (technoflora)
```

**Half-duplex** между:
- Text → TTS → audio
- Marker → Commander → MCU

**Proactive mode.** Командный контур может работать БЕЗ внешней реплики — при долгом отсутствии активности, фоновых изменениях, периодическом сканировании среды.

---

## Сценарий взаимодействия (3.3.4)

### 4 режима поведения:

1. **Явный отклик.** Зритель говорит → ASR → LLM → TTS + MCU.
2. **Фоновая реакция.** Изменение света/звука при присутствии без обращения.
3. **Ожидание.** Снижение активности при отсутствии зрителя, но не полное отключение.
4. **Проактивное проявление.** Спонтанная реплика или паттерн технофлоры при выполнении внутренних условий.

### Engagement levels (из VLM prompt):
- none
- watching
- approaching
- leaving
- interacting

---

## Expected Code Correspondences

| Diploma | Adam Chip |
|---|---|
| VAD | `System/adam/webrtc_vad.py` |
| Wake word | `System/adam/wake_word.py` (openwakeword) |
| ASR.py | `System/Speech/ASR_WhisperX.py` |
| TTS.py | `System/Speech/TTS.py` (Silero) |
| Visual scene | `System/adam/inference.py` (SceneWorker) + camera.py (CameraReader) |
| Orchestrator | `System/Orchestrator.py` (VoiceLoopController) |
| Commander.py | `System/adam/action.py` (ActionLayer) |
| Communication.py | `System/adam/device.py` (MCUClient) |
| Proactive mode | (?) — проверить наличие idle scheduler в Stage 2 |

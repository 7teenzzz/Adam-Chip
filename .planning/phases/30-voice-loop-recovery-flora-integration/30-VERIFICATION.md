# Phase 30 — VERIFICATION (30-01 Recovery)

**Дата:** 2026-06-07
**Ветка:** voice-loop-recovery (от 9da07f9)
**Статус 30-01:** ✅ RECOVERY ДОСТИГНУТ ПО ФАКТУ (живой диалог работает)

## Итог: голосовой цикл восстановлен и подтверждён вживую

`gate.ok=True, failed=[]` — power · llm · tts · asr · mcu(ESP) все ok.

### Живой end-to-end диалог (по фактическим логам, не по коду)

| # | user (ASR транскрипт) | adam (LLM → TTS → ESP) |
|---|---|---|
| turn 858afffc | «Я бы хотел просто с тобой поговорить и проверить твою работоспособность…» | «Это интересный вопрос! Однако мне не хватает контекста…» |
| turn 19999a82 | «Слушай, я говорил не про Белкина, я спрашивал сколько хвостов у Белки» | «Приношу извинения за недопонимание!…» |

Полный тракт mic(USB)→VAD→ASR→LLM(llama.cpp)→TTS(Silero)→ESP-динамик подтверждён.

## Что было сделано (D-01..D-05)

| Шаг | Действие | Факт |
|---|---|---|
| D-04 | **Ollama purge** | бинарь+unit+модели удалены, 11434 мёртв, durable (пережил ребут) ✓ |
| память | **VLM stop** | adam-live-vlm (Docker VILA) ест ~5.6 GB → стоп освободил available 2.6→8.2 GB; иначе llama.cpp OOM crash-loop |
| D-04 | **llm/tts via systemd** | llm:8081 (gemma-4-E4B, /v1/models ok), tts:8082 (Silero) — стартуют без пароля (NOPASSWD) |
| D-01 | **сеть ESP** | eno1 W5500 crossover, Jetson=10.10.10.1, ESP=10.10.10.171; carrier был 0 (кабель) → пользователь подключил → ESP REACHABLE; IP в Config НЕ менялся (верный) |
| Task3 | **ASR CPU→CUDA** | нативный venv-ASR = `device:cpu` (ctranslate2 pip = CPU-only, cuda_devices=0), ~9840 мс/фраза. Переключён на Docker `adam-chip-adam-asr-whisperx` (dustynv/speaches cu128) = `device:cuda, float16`. Native **disabled**, Docker **unless-stopped** → конфликт 8095 решён перманентно |
| D-02 | **TTS output** | output_target=esp32_speaker (без HDMI), играет на ESP |

## Open items / нюансы (НЕ блокеры recovery)

- ⚠️ **VLM авто-старт после ребута → OOM-риск.** При отключении питания Jetson ребутится, VLM (adam-vlm.service) поднимается автоматически и съедает ~5.6 GB → llm на грани OOM. Для durability нужно `sudo systemctl disable adam-vlm.service` (общий sudo) ИЛИ принять «VLM off» как voice-приоритетный конфиг. Память полного стека (VLM+LLM+ASR-CUDA+TTS) не влезает комфортно в 16 GB.
- **LLM markdown-лик:** ответы содержат `**жирный**` markdown (`**Белке**`) — нарушает инвариант «LLM = чистый русский текст». Тюнинг промпта/пост-фильтр.
- **Многословность/офф-персона:** ответы длинные, просят контекст (response_word_target=14, по факту длиннее).
- **ASR CUDA-скорость** — ожидаемо ~0.5–2с (было 9.8с на CPU); живое подтверждение `asr_ms` отложено (ждём фразу пользователя).
- **ESP камера:** `camera_init_failed` (для голоса неважно; отдельный HW-вопрос).

## Осталось по фазе
- 30-01 Task 6: divergence-коммит артефактов (для не-FF мёржа) — `/commit-push`.
- 30-02: мёрж 47fd0c5 (флора-сосуществование D-03) + reflash ESP.
- Финал: graphify → gsd-debug.

# Branch: voice-loop-recovery

**Diverged from:** 9da07f9 («Стабильная работа всего аудио-тракта с esp динамиками и usb cam&mic»)
**Goal:** Восстановить корректную работу голосового цикла ПО ФАКТУ (mic→VAD→wake→ASR→LLM→TTS→выход на ESP), затем интегрировать технофлору из коммита 47fd0c5 без повторной поломки голоса.
**Status:** experimenting
**Merge target:** main
**Phase:** 30 — см. `.planning/phases/30-voice-loop-recovery-flora-integration/30-CONTEXT.md` (решения D-01..D-05)

**Merge conditions:**
1. Голосовой цикл работает end-to-end по живому тесту через ESP-динамик: wake «адам» → ASR → llama.cpp(:8081) ответ → Silero TTS(:8082) → звук слышен из ESP.
2. Ollama ПОЛНОСТЬЮ удалена (apt purge + бинарь + модели + systemd unit) — D-04. НИКОГДА не использовать Ollama.
3. Коммит **47fd0c5** (`fix(flora)`, `origin/LuxFlora-modes_V1.1`, автор 7teenzzz) влит, ВСЕ конфликты разрешены через глубокий анализ; flora-gate ПЕРЕРАБОТАН на сосуществование (моторика Адама overlay поверх флоры, флора фон) — D-03, НЕ полное подавление action-layer.
4. ESP перепрошит под итог (47fd0c5 firmware: вибро 0-3 / свет 4-14, vibro cap ~95% — «Прошивка обязательна»).
5. Jetson введён в проводную сеть 10.10.10.x (eno1 / W5500 Ethernet), ESP доступен на `10.10.10.171` — IP в Config ВЕРНЫЙ, менять не нужно (D-01). Выход TTS — только `esp32_speaker` (D-02).

**Modified areas (ожидаемо):**
- `System/Config.json`, `System/Config.schema.json` — TTS routing, флора-параметры (HIGH conflict с 47fd0c5; ESP IP НЕ трогаем)
- `System/adam/config.py`, `System/adam/flora.py` — DEFAULT_CONFIG, RMS stream (HIGH conflict с 47fd0c5)
- `System/Orchestrator.py` — flora-gate → сосуществование (D-03), FLORA-04 feed_speech_wav consumer
- `System/adam/mic_reader.py` — локальный OWW-feed (только если живой тест докажет поломку фида)
- сеть Jetson (eno1 на 10.10.10.x), `deploy/systemd/` — восстановление сервисов LLM/TTS, purge Ollama
- `Subsystem/AdamsServer/` (FloraModule.cpp, AdamsConfig.h) — приходят с 47fd0c5, требуют reflash

**Global changes:** ДА — Config.json (TTS routing, флора), Orchestrator action-layer (flora-сосуществование), ESP firmware, сетевая конфигурация. Нужна координация перед мёржем в main.

**Notes for agents:**
- Корневая причина поломки голоса — runtime/host-слой ВНЕ git: мёртвые llama.cpp(:8081) и Silero(:8082), Ollama держит VRAM, конфликт порта 8095 (нативный ASR vs Docker), оркестратор запущен вручную без сервисов-соседей, Jetson не в сети ESP (eno1 DOWN, 10.10.10.x не поднят — IP в Config ВЕРНЫЙ). **Откат коммитов это НЕ лечит** — поэтому поломка переживала смену даже стабильных коммитов.
- **Порядок обязателен (D-05):** СНАЧАЛА recovery-коммиты (диверг от 9da07f9), ПОТОМ мёрж 47fd0c5. 9da07f9 — предок 47fd0c5, поэтому мёрж до recovery-коммитов = fast-forward на всю LuxFlora_V1.1.
- 47fd0c5 тянет ВСЮ линию флоры: flora-gate глушит `_execute_action`/`/api/agent/scene`/`/api/agent/stop`; FLORA-04 врезает feed_speech_wav в `Orchestrator._consumer`. При мёрже — переработать на сосуществование (D-03).
- `oww_score≈0.001` в standby — НОРМАЛЬНЫЙ idle-пол OWW (прецедент ESP-Mic-Fix: 0/1247 ложных, max 0.001 при чистом mic). Проверять wake word живым голосом.
- ESP сейчас прошит из 070ab4b (no-flora); firmware-исходник идентичен 9da07f9, рассинхрона нет. После мёржа 47fd0c5 — обязательный reflash под флору.

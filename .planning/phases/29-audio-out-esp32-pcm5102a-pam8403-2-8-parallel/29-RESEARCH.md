# Phase 29: Audio Out на ESP32 динамики — Research

**Researched:** 2026-05-18
**Domain:** TTS routing flip (HDMI → ESP32 PCM5102A) + analog amp chain bring-up (PAM8403 + 2×8Ω parallel per channel)
**Confidence:** HIGH (всё, что нужно планнеру, — это codebase-факты, locked decisions уже сделаны)
**Branch:** `V-S09.1-Audio_out`

---

## Summary

Phase 29 — это **последняя миля** заранее написанного software-маршрута: функция `TTSClient._play_wav_bytes_to_esp32_sync` (`System/adam/inference.py:348-404`) и ESP firmware-handler (`Subsystem/AdamsServer/src/web/WebServerModule.cpp:2529-2603`) уже существуют, протестированы в Phase 8/9 на breadboard и сейчас ждут пайки реального аналогового тракта. Все инженерные решения (параллель 4Ω, делитель 1:6, software cap 1.0, общая 5V с ESP, ramp 0.5→1.0) зафиксированы в `29-CONTEXT.md <decisions>` и не пере-исследуются.

**Что планнер должен унести из этого документа:**

1. **Per-criterion validation map** — каждый из 8 acceptance criteria измерим конкретной командой/файлом/значением.
2. **Defensive tasks** — ESP firmware устроен «нет mute-pin / нет stop-endpoint», без аккуратных pre-checks Wave 1 рискует получить громкий pop при включении или сожжённый минус канала.
3. **Wave-ordering критика** — текущий план в CONTEXT.md в основном корректен, но Wave 2 (config cap) безопасно поднять выше: можно сделать его pre-flight для всего hardware-этапа.
4. **Smoke-test artifact spec** — точная команда `sox` для генерации `test_440hz_-12dbfs.wav` (`sox` уже в системе, `ffmpeg` нет — учитывать).
5. **Code citation index** — file:line ссылки для PLAN.md task descriptions.

**Primary recommendation:** Планнер делает 7 волн как в CONTEXT.md, но **Wave 2 (schema cap + Config.json starter volume) выполняется ДО Wave 1 (пайка)**. Это защищает железо: если оператор по привычке ребутнёт оркестратор посреди пайки, software-cap уже на 1.0 и стартовое 0.5.

---

## User Constraints (from 29-CONTEXT.md)

### Locked Decisions (НЕ переисследовать)

**Hardware topology:**
- Параллель 8 ∥ 8 = 4 Ω на канал (4 × 1W динамики 2209)
- Резистивный делитель 1:6 на канал: R1=10 кОм + R2=2 кОм (после PCM5102A LOUT/ROUT, перед PAM8403 INL/INR)
- BTL-ограничения: `−OUT_L ≠ −OUT_R`, никакой `−OUT_x` ≠ GND, плюсы не соединять
- Питание PAM8403: общая 5V ветка с ESP через тот же step-down + local decoupling 100 µF + 100 nF
- LC-фильтр питания — только revisit если Wave 3 покажет шум

**Software / Config:**
- `services.tts.output_target`: `"jetson_hdmi"` → `"esp32_speaker"` ТОЛЬКО после Wave 3 PASS (требует рестарт `adam-orchestrator.service` — читается в `TTSClient.__init__`, `inference.py:213-224`)
- `tuning.voice.volume` старт: `0.5`; ramp 0.5 → 0.7 → 0.85 → 1.0 в Wave 5
- `Config.schema.json` `tuning.voice.volume.maximum`: `2.0` → `1.0` (currently at line 947, `"maximum": 2.0`)
- `safety.half_duplex_mute = true` — остаётся
- `services.asr.post_tts_discard_window_ms = 2500` — оставляем, ре-валидация в Wave 6

**Acceptance signal:** Голос Адама звучит из корпуса, не клиппит на 1.0, динамики не нагреваются за 30 мин, self-echo не приводит к ложным `asr_result`.

### Claude's Discretion

- Failover-инструкция в RUNBOOK — стандартная exhibition-практика
- `post_tts_discard_window_ms` — оставить 2500, ре-валидация эмпирически
- Barge-in принят как V1 limitation

### Deferred Ideas (OUT OF SCOPE)

- Barge-in для esp32_speaker (требует firmware-фазы: `POST :81/api/speaker/stop`)
- UI tuning slider refresh после смены ceiling
- Стерео-эффекты / scene-driven audio cues
- Окружающий звук / эмбиент

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| WAV resample 24000→44100 + mono enforce | Jetson Python (`inference.py:_prepare_wav_for_esp32_speaker`) | — | ESP firmware рассчитан строго на `audio/wav 44100/mono/16` и rejects mismatched header с HTTP 400 (`WebServerModule.cpp:2569-2574`). Resample делать на Jetson дешевле. |
| WAV `volume` gain (software cap) | Jetson Python (`Orchestrator._apply_wav_volume`, line 172) | Config.schema.json `tuning.voice.volume.maximum` | Software-cap = defense-in-depth; hardware-cap = резистивный делитель. Оба нужны. |
| I2S Philips DMA → PCM5102A | ESP firmware (`AudioModule.cpp:initSpeakerStdTxChannel`, line 342) | — | I2S_NUM_1 master mode, BCLK=38, LRCK=39, DATA=40, MCLK=GND. |
| BTL drive 2.9 V→ ~3.2W/4Ω | PAM8403 chip | — | Class-D, gain ×16. Без делителя 1:6 = hard clip от PCM5102A 2.1 Vrms. |
| `tts_finished` synchronisation | Jetson Python (`_play_wav_bytes_to_esp32_sync` sleep loop, lines 396-399) | — | ESP firmware **отдаёт HTTP 200 как только тело принято в ring**, до завершения I2S drain. Jetson sleep'ит на `duration_sec - elapsed`, чтобы `last_tts_finished_at` соответствовал реальному моменту окончания звука (важно для `post_tts_discard_window`). |
| Half-duplex mute (мик заглушен во время TTS) | Jetson Python (`Orchestrator.py:979` `mic_muted` event, `MicReader.set_muted`) | — | Инвариант `safety.half_duplex_mute=true`. Физическая близость динамика-к-мику через корпус делает self-echo неизбежным без mute. |

---

## Standard Stack

### Hardware BOM (Wave 1)

| Item | Quantity | Note |
|------|----------|------|
| Резистор 10 кОм 1/4W 5% | 2 | R1 для L и R канала делителя |
| Резистор 2 кОм 1/4W 5% | 2 | R2 для L и R канала делителя |
| Электролит 100 µF 10V | 1 | Локальный decoupling PAM8403 VDD |
| Керамика 100 nF | 1 | High-frequency decoupling, параллельно электролиту |
| Динамик 8Ω 1W (2209 или аналог) | 4 | По 2 на канал параллельно |
| (резерв) дроссель 10–47 µH | 1 | Только если Wave 3 покажет шум от моторов |
| (резерв) электролит 470 µF | 1 | Совместно с дросселем — LC-фильтр питания |

### Software stack уже в проекте (не трогать)

| Module | File:line | Purpose |
|--------|-----------|---------|
| WAV preparation | `inference.py:75-92` (`_prepare_wav_for_esp32_speaker`) | Validate header → mono-downmix → resample → rebuild 44-byte header |
| WAV parser | `inference.py:42-72` (`_parse_wav`) | Chunk walker (LIST/JUNK-resilient) |
| ESP POST | `inference.py:348-404` (`_play_wav_bytes_to_esp32_sync`) | POST + duration-sleep sync |
| `_NO_PROXY_OPENER` | `inference.py:20` | Bypass v2ray для ESP32 LAN (см. CLAUDE.md Gotchas) |
| Routing switch | `inference.py:274-278` (`_play_wav_bytes_sync`) | `if output_target == "esp32_speaker": …` |
| `output_target` validation | `inference.py:204, 213-224` | Schema enum-only, runtime fallback to `jetson_hdmi` на typo |
| WAV gain | `Orchestrator.py:172` (`_apply_wav_volume`) | `audioop.mul`; `>1.0` уже клиппит samples |
| Volume read per-chunk | `Orchestrator.py:2684-2688` (`_current_volume`) | Reads `tuning_store.current().voice.volume` каждый chunk (hot-reload) |
| ESP `/speaker` handler | `WebServerModule.cpp:2529-2603` | Reject mismatch → HTTP 400, ring buffer + pacing |
| ESP I2S init | `AudioModule.cpp:342-386` (`initSpeakerStdTxChannel`), `714-756` (`initSpeakerPlayback`) | Philips 16-bit stereo, slot_mask=BOTH (mono WAV → L=R) |

**Installation:** Никаких новых Python-пакетов. `sox` уже доступен на Jetson (для генерации smoke WAV). `ffmpeg` отсутствует — учесть в Wave 3.

---

## Validation Architecture

> Mandatory for Nyquist Dimension 8. Per-criterion measurement strategy для всех 8 acceptance criteria из `29-CONTEXT.md <verify>`. **Nyquist enabled** (config.json не задаёт `workflow.nyquist_validation: false`).

### Test Framework Map

| Property | Value |
|----------|-------|
| Тип тестов | Hardware acceptance (manual + automated probes) + event-log assertion |
| Python test runner | pytest (минимально; основная валидация — manual + curl + jq) |
| Логи как source of truth | `data/adam/events.jsonl` (parse with `python3 scripts/adam_pull_logs.py` или `jq`) |
| Sample WAV для Wave 3 | `tests/fixtures/test_440hz_1s_-12dbfs.wav` (создать в Wave 3) |

### Criterion → Test Map

#### Wave 1 / C1: «омметр показывает 4 Ω на каждой паре `+OUT_x` / `−OUT_x`; нет КЗ минусов на GND»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | Мультиметр в режиме Ω. PAM8403 **обесточен** (питание отключено!). Между `+OUT_L` ↔ `−OUT_L` — должно быть ≈ 3.6–4.2 Ω (теоретические 4 Ω + сопротивление проводов). Между `−OUT_L` ↔ GND — должно быть **OL / >1 МΩ** (открытая цепь). Между `−OUT_L` ↔ `−OUT_R` — должно быть **OL**. Между `+OUT_L` ↔ `+OUT_R` — должно быть **OL**. |
| **Pass** | 3.6 ≤ R_L ≤ 4.2 Ω **И** 3.6 ≤ R_R ≤ 4.2 Ω **И** все cross-checks показывают OL |
| **Fail (low R, ~2Ω)** | Динамики соединены параллельно дважды (вместо два параллельных динамика — четыре). Топологическая ошибка пайки. |
| **Fail (high R, >8Ω)** | Динамики в серию, не параллель. Звук в 2× тише. |
| **Fail (короткое −OUT/GND или −OUT_L/−OUT_R)** | **СТОП. НЕ ВКЛЮЧАТЬ ПИТАНИЕ.** PAM8403 BTL — конкат `−OUT` к чему-либо кроме своего динамика спалит чип. |

#### Wave 1 / C2: «PAM8403 питается без видимого спайка при включении моторов»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | Подать на ESP `POST :80/api/pca/channel` с резким импульсом (`channel: 0, value: 4095`). Идеально — осциллограф на VDD PAM8403 (масштаб 1V/div, 1ms/div). Без осциллографа — **слух**: подать на speaker 440Hz синус через `curl POST :81/speaker --data-binary @test_440hz_1s.wav` параллельно с импульсом мотора. Слышен ли треск/щелчок в тон с PWM. |
| **Pass** | Спайк на VDD < 200 мВ (если есть осциллограф); слышимых щелчков нет; синус остаётся чистым |
| **Fail (видимый спайк >500 мВ или слышимый треск)** | Decoupling 100 µF + 100 nF недостаточен. Wave 1 revisit: LC-фильтр (10–47 µH + 470 µF) между step-down и VDD PAM8403, либо разделение веток. |
| **Root cause hint** | PAM8403 Class-D переключается на ~250 кГц — питание чувствительно к ВЧ-помехам PCA9685 PWM. Электролит 100 µF гасит низкие частоты, керамика 100 nF — высокие. Если шумит — добавить вторую керамику ближе к pin. |

#### Wave 3 / C3: «`curl -X POST :81/speaker --data-binary @test_440hz.wav` → HTTP 200, чистый синус без хрипа»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | `curl -v --noproxy '*' -X POST -H "Content-Type: audio/wav" --data-binary @tests/fixtures/test_440hz_1s_-12dbfs.wav http://192.168.0.171:81/speaker` (см. Smoke-Test Artifacts ниже для генерации WAV). Параллельно поднести телефон с камерой/диктофоном к динамикам — записать выход и спектрально посмотреть. |
| **Pass** | HTTP `200 {"status":"ok"}`; на слух — стабильная нота 440 Hz без модуляции; на спектре (Audacity / `sox stat`) пик 440 Hz, без явного 50/60 Hz hum, без гармоник выше -30 dBFS |
| **Fail (HTTP 400 `speaker_wav_format_mismatch`)** | WAV сгенерирован неправильно — не 44100/mono/16-bit (см. `WebServerModule.cpp:2569-2574` для exact rejection). Регенерировать через `sox` со строгими параметрами (см. ниже). |
| **Fail (HTTP 503 `speaker_not_ready`)** | ESP не дошёл до `initSpeakerPlayback()` — посмотреть serial log COM6 на `bootLog("speaker", ...)`. Возможна collision на I2S_NUM_1. |
| **Fail (HTTP 409 `speaker_sink_busy`)** | Параллельный запрос ещё идёт — `beginSpeakerStream()` mutex держится. Дождаться и повторить. |
| **Fail (HTTP 200, но звук с треском/хрипом)** | Аналоговая часть: проверь делитель (R1=10к на ESP стороне, R2=2к на GND стороне — НЕ перепутать); измерить Vpp на INL/INR (должно быть ~1.0 Vpp при -12 dBFS вход). |
| **Fail (HTTP 200, но звук с модуляцией от моторов)** | Питание — см. C2 mitigation (LC-фильтр). |

#### Wave 4 / C4: «`output_target=esp32_speaker` + live `/api/agent/turn` → голос разборчивый»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | После flip Config + restart `adam-orchestrator.service`: `curl --noproxy '*' -X POST http://127.0.0.1:8080/api/agent/turn -H 'Content-Type: application/json' -d '{"transcript":"Адам, проверка связи. Ты меня слышишь?"}'`. Параллельно слушать корпус. |
| **Pass** | Слышен голос Адама из корпуса (не HDMI!) **И** в `events.jsonl` запись `{"event":"tts_finished","target":"esp32_speaker","ok":true,...}` **И** разборчивость subjectively ≥ «8/10» (слова чёткие, нет roboticness/clipping) |
| **Fail (звук из HDMI, не корпуса)** | `output_target` не применён. Проверь: `python3 -c "from System.adam.config import Settings; print(Settings.load().section('services')['tts'])"`. Если значение там правильное — orchestrator не рестартовали (значение читается в `TTSClient.__init__`, не hot-reload). |
| **Fail (тишина, HTTP 200 logged)** | ESP принял запрос, но звук не идёт. (a) проверь `gRuntimeState.speakerReady` через `:80/api/status`; (b) проверь питание PAM8403 (5V на VDD); (c) проверь, что динамики физически подключены. |
| **Fail (звук есть, но хриплый/искажённый)** | `tuning.voice.volume` слишком высок ИЛИ делитель собран без R2 (получили unattenuated 2.1 Vrms на вход PAM8403 = hard clip). |

**WARNING for planner:** CONTEXT.md в Wave 6 пишет «10 последних `tts_played` в `events.jsonl`», но реальный event-name **`tts_finished`** (см. `Orchestrator.py:2939`, `2950`, `2954`). Никакого `tts_played` в коде нет. Также `target=esp32_speaker` в самом event payload **не пишется** на уровне Orchestrator — только внутри `_play_wav_bytes_to_esp32_sync` return dict (`inference.py:401`). Планнер должен либо (a) добавить `"target": tts.output_target` в `tts_finished` payload (см. `Orchestrator.py:2939`), либо (b) переписать критерий: «по `tts.output_target` из startup-логов + 10 последних `tts_finished` все `ok=true`».

#### Wave 5 / C5: «`tuning.voice.volume=1.0` — нет клиппинга на длинных гласных»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | Поднять `tuning.voice.volume` через `curl :8080/api/config -X PATCH -H 'Content-Type: application/json' -d '{"tuning":{"voice":{"volume":1.0}}}'` (hot-reload — читается каждый chunk через `_current_volume()`, см. `Orchestrator.py:2684`). Прогнать длинную фразу с гласными «о»/«а»/«у» (тестовая фраза: «Здравствуй. Я — Адам. Сегодня я наблюдаю людей вокруг этой инсталляции…»). Записать на телефон. В Audacity посмотреть на waveform: есть ли «отсечённые» пики (плоские топы на ±32767). |
| **Pass** | Waveform peaks НЕ обрезаны (нет плоских участков на максимуме амплитуды) **И** на слух нет «жжёного» хрипа на длинных гласных |
| **Fail (clipped peaks)** | Software-cap нужно опустить (попробовать 0.85). Возможно, делитель надо пересчитать — у Silero RMS-level не одинаков между голосами (eugene громче чем kseniya). Если планнер хочет — увеличить R1 c 10к до 15к (дальнейшее ослабление до 1:7.5). |
| **Fail (нет клиппинга, но голос всё ещё тише желаемого)** | Это OK для V1. PAM8403 на 5V с делителем 1:6 даёт ~70% от теоретического выхода 4Ω = ~2.2W/канал = достаточно для выставочного зала. Поднимать через increase R2 не нужно — лучше работать на инвариантах. |

#### Wave 5 / C6: «динамики не нагреваются после 30 мин непрерывного диалога»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | Запустить сценарий «длинный диалог»: цикл `for i in {1..60}; do curl :8080/api/agent/turn -d '{"transcript":"расскажи о себе"}'; sleep 30; done` (≈ 30 мин). После — потрогать (a) каждый из 4 динамиков рукой, (b) корпус PAM8403 |
| **Pass** | Динамики «комнатной температуры или чуть теплее» (< 40 °C на ощупь). PAM8403 «тёплый, но не горячий» (< 60 °C). |
| **Fail (динамики >50 °C)** | Mean RMS power превышает 1W rating. Опустить volume cap (0.85). Возможно делитель собран с обратными резисторами (R1=2к, R2=10к = усиление вместо ослабления). |
| **Fail (PAM8403 chip-hot, >70 °C)** | Чип на пределе. Либо плохой decoupling (греется от ВЧ-возбуждения), либо нагрузка <4Ω (динамики параллельны больше чем по 2). Не оставлять под нагрузкой. |
| **NOTE for planner** | Этот критерий — **long-running**, не вписывается в одну итерацию execute. Планнер должен сделать его отдельной задачей в Wave 5 с явным `Verify: human-in-the-loop 30-min monitor`. Зачёт принимает оператор после прогона. |

#### Wave 6 / C7: «10 последних `tts_played` в `events.jsonl` все `target=esp32_speaker ok=true`»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | Команда (после ≥10 turns): `jq -c 'select(.event=="tts_finished")' data/adam/events.jsonl \| tail -10`. Проверить, что каждая запись имеет `ok: true`. **Дополнительно:** добавить `"target": tts.output_target` в `Orchestrator.py:2939` payload (см. C4 warning) — это уже маленькая полезная правка кода в рамках Wave 4/6. |
| **Pass** | Все 10 записей `tts_finished` имеют `ok: true`; нет `degraded: true`; нет `tts_chunk_failed` событий вперемешку |
| **Fail (`ok: false` где-то)** | Поднять из лога `body`/`error` от ESP. Возможные: TCP RST (ESP перезагрузился), HTTP 400 (вернулся `wav_format_mismatch` — Silero сгенерировал что-то не 24000? проверь `services.tts.sample_rate`), HTTP 503 (`speaker_not_ready` — I2S не поднялся). |
| **Fail (`tts_chunk_failed` записи)** | TTSClient `/wav` endpoint вернул `None` (`inference.py:264-272`); это до ESP, проблема в Silero. Лечится отдельно. |

#### Wave 6 / C8: «0 `asr_result` событий с timestamp в окне `[tts_start, tts_end + post_tts_discard_window_ms]`»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | Скрипт-проверка по `events.jsonl`: для каждой пары (`tts_started`, ближайший последующий `tts_finished`) сформировать окно `[t_start, t_finished + 2.5s]`. Внутри окна не должно быть `asr_result` событий. Можно одной командой `jq`: см. snippet ниже. |
| **Pass** | 0 `asr_result` в окне (для последних ≥10 turn-ов) |
| **Fail (1-2 `asr_result` за 30 мин)** | `post_tts_discard_window_ms=2500` маловато для нового self-echo. Увеличить до 3000-3500. CONTEXT.md в Discretion явно разрешает revalidate. |
| **Fail (несколько `asr_result` в окне на каждый turn)** | Acoustic coupling сильнее ожиданий. (a) проверь `safety.half_duplex_mute=true` (мут должен работать через `mic_muted` event, см. `Orchestrator.py:979`); (b) проверь, что MicReader действительно блокирует chunks — должен быть `mic_unmuted` event ровно через discard window после `tts_finished`. Если discard work'ает, но `asr_result` всё ещё прорывается — это значит **TTS-tail audio лагает в ESP DMA дольше, чем `_play_wav_bytes_to_esp32_sync` ждёт**. Mitigation: добавить запас 200-500ms в Jetson sleep (`inference.py:399`) ИЛИ поднимать discard_window. |

**Verification snippet для C8 (для PLAN.md task):**

```bash
# Pairs (tts_started, tts_finished) + assert no asr_result within
python3 - <<'PY'
import json
from pathlib import Path
events = [json.loads(l) for l in Path("data/adam/events.jsonl").read_text().splitlines() if l.strip()]
discard_ms = 2500
violations = 0
i = 0
while i < len(events):
    if events[i].get("event") == "tts_started":
        t_start = events[i].get("ts", 0)
        # find next tts_finished
        for j in range(i+1, len(events)):
            if events[j].get("event") == "tts_finished":
                t_end = events[j].get("ts", 0)
                window_end_ms = t_end * 1000 + discard_ms
                # check for asr_result within window
                for k in range(i+1, len(events)):
                    if events[k].get("event") == "asr_result":
                        tk = events[k].get("ts", 0) * 1000
                        if t_start * 1000 <= tk <= window_end_ms:
                            violations += 1
                            print(f"VIOLATION: asr_result at {tk} in [{t_start*1000}, {window_end_ms}]")
                i = j
                break
    i += 1
print(f"Total violations: {violations}")
PY
```

#### Wave 7 / C9: «`docs/RUNBOOK_JETSON_EXHIBITION.md` обновлён, секция «Аудио-маршрут»»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | `grep -n "## Аудио" docs/RUNBOOK_JETSON_EXHIBITION.md` возвращает ≥1 строку; `git log --oneline docs/RUNBOOK_JETSON_EXHIBITION.md \| head -5` показывает phase-29 commit |
| **Pass** | Секция содержит: (a) топологию (4Ω parallel, делитель 1:6), (b) команды для проверки speakerReady (`curl :80/api/status \| jq .speaker_ready`), (c) failover-процедуру (как откатить на `jetson_hdmi`), (d) BOM ссылку в CONTEXT.md |
| **Fail** | Не хватает любого из (a)-(d). Минимальный размер ~30 строк. |
| **Existing RUNBOOK structure** | Sections (от line 1): Power Gate / Local Runtime / Docker Runtime / Production Systemd Runtime / Media Policy / TTS Dependencies / Gate-To-Green Sequence / Smoke Checks / Reply hang diagnosis. **Логичное место для новой секции — между «Media Policy» (line 88) и «TTS Dependencies» (line 96)**, ли названием `## Audio Output Path (ESP32 Speaker)`. |

#### Wave 2 / C10: «`Config.schema.json` `tuning.voice.volume.maximum = 1.0`, описание обновлено»

| Aspect | Detail |
|--------|--------|
| **Как измерить** | `jq '.properties.tuning.properties.voice.properties.volume.maximum' System/Config.schema.json` возвращает `1.0`. Описание содержит слова «hardware-chain» или «PAM8403» или «1W rating». |
| **Pass** | Текущая строка `System/Config.schema.json:947` `"maximum": 2.0` поменяна на `"maximum": 1.0` **И** description обновлён. |
| **Fail** | Schema не отредактирована или description не упоминает железо — оператор не поймёт, **почему** cap опущен. |
| **Bonus check** | Pydantic-модель в `System/adam/tuning.py` — проверь, нет ли там зашитого `Field(..., le=2.0)`, иначе schema-only изменение не enforced. Quick scan: `grep -n "volume" System/adam/tuning.py`. |

---

## Integration Pitfalls

### Pitfall 1: PCM5102A line-out boot-time pop / startup transient

**What goes wrong:** PCM5102A при холодном подключении 3.3V и одновременно отсутствии I2S clock может выдать DC-offset на LOUT/ROUT на ~30-50 мс до того, как `i2s_channel_enable()` (line 377) запустит SCK/WS. Это идёт через делитель 1:6 → на PAM8403 INL/INR появляется DC-step → PAM8403 усиливает → щелчок в динамиках при boot.

**Why it happens:** Firmware **не использует** XSMT (mute pin) PCM5102A — на схеме pin указан как `MCLK → GND`, а XSMT обычно прибинден к GPIO для mute control. В нашей PinsConfig.h XSMT pin не определён. У PCM5102A есть internal soft-mute, но он не покрывает power-up transient.

**How to avoid:** **Hardware mitigation**: Wave 1 должен заземлить XSMT через 10 кΩ pull-down (если pin XSMT доступен на модуле — на BoB-модулях он обычно выведен на header). **Software workaround** (если pin недоступен): Wave 1 задерживает подключение PAM8403 power-on до завершения ESP boot (использовать MOSFET-switch на 5V PAM, управляемый GPIO; перенесено в deferred — V2 если pop слышен).

**Warning signs:** Чёткий щелчок длительностью 30-80 мс в момент `bootLog("speaker", "ready...")` (line 754). Если щелчок слабый — игнорировать; если громкий и регулярный — Wave 1 revisit.

### Pitfall 2: PAM8403 BTL output short

**What goes wrong:** Оператор паяет минусы каналов вместе для «общей земли» (привычка с обычных однопроводных усилителей) → PAM8403 BTL — оба `-OUT` это активные anti-phase сигналы. Соединение `-OUT_L ↔ -OUT_R` мгновенно сжигает выходные транзисторы (или термозащита, если повезло).

**Why it happens:** На large-scale PCB обычно один GND. PAM8403 datasheet figure 7 показывает «no common ground for speakers», но это легко пропустить.

**How to avoid:** Wave 1 explicit pre-power test: омметр между `-OUT_L`↔`-OUT_R`, `-OUT_L`↔GND, `-OUT_R`↔GND — все три должны быть OL (>1 МΩ). Включать питание ТОЛЬКО после прохождения этого теста. CONTEXT.md C1 уже это покрывает — планнер должен сделать это **первым** sub-таском Wave 1, ДО любого включения 5V.

### Pitfall 3: Sample-rate handshake (Silero 24000 → resampler → ESP 44100)

**What goes wrong:** Silero v5_5_ru даёт `services.tts.sample_rate=24000`. `_prepare_wav_for_esp32_speaker` (inference.py:75-92) resample'ит 24000 → 44100. Если Silero вдруг отдаст что-то другое (например, после firmware/model update на 48000), validation `audio_format != 1 or bits != 16` (line 82) не поймает — он проверяет только bits/format, **не sample_rate**. Resampler примет любую частоту источника и сделает 44100 на выходе. Но если внутри Silero на каком-то этапе вылетит non-PCM формат — будет `ValueError("unsupported PCM format=...")` (line 83).

**ESP rejection:** ESP firmware (WebServerModule.cpp:2569-2574) проверяет header **точно** на 44100/mono/16, возвращает HTTP 400 `speaker_wav_format_mismatch`. **Silent failure не происходит** — это hard reject. Это хорошо: если что-то ломается, мы видим HTTP 400 в Jetson-логах.

**How to avoid:** Wave 3 включает explicit check: первый `curl /speaker` — это намеренно неправильный WAV (например, 48000 Hz), убедиться, что ESP возвращает 400 (negative test). Это даёт уверенность в error-handling до того, как начнём слать живой TTS.

### Pitfall 4: `_prepare_wav_for_esp32_speaker` edge cases

Анализ inference.py:75-92:

- **Mono input, 24000 Hz, 16-bit** (normal Silero output): downmix skipped, resample applied. ✓
- **Stereo input, 16-bit**: `audioop.tomono(pcm, 2, 0.5, 0.5)` (line 88). Корректно.
- **Mono 44100 Hz**: skip downmix, skip resample (line 89 falsy). Корректно.
- **Empty PCM** (`data_size=0`): `_build_wav_header(0, ...)` — валидный 44-байтный header без data. ESP firmware `remaining = req->content_len` → `while (remaining > 0)` пропустит цикл, вернёт HTTP 200. Корректно (no-op).
- **3-channel, 4-channel input**: raises `ValueError(f"unsupported channels={channels}")` (line 85). Корректно.
- **24-bit / 32-bit input**: raises `ValueError(f"unsupported PCM format=... bits=...")` (line 83). Корректно — Silero не выдаёт такое.
- **Очень короткий clip (<10 мс)** или **filler «Хм...»**: проходит через тот же путь. ESP firmware pace'ит запись (4 мс vTaskDelay, line 2590) — короткий clip всегда влезает в первый ring-fill. OK.

**Conclusion:** `_prepare_wav_for_esp32_speaker` устойчиво. Нет нужды в дополнительной defensive task'е.

### Pitfall 5: half_duplex_mute path и duration sync

**Where mute is enforced:** `Orchestrator.py:979` (`event_log.append("mic_muted", ...)`) и `Orchestrator.py:997-1020` для unmute. Logic — MicReader при `mic_muted=true` отбрасывает frames до тех пор, пока (a) `mic_unmuted` event + (b) `post_tts_discard_window_ms` не истекут.

**Critical:** Mute window grows with TTS duration. `_play_wav_bytes_to_esp32_sync` (inference.py:396-399) **блокируется на duration_sec**, благодаря чему `runtime_state["last_tts_finished_at"] = time.perf_counter()` (Orchestrator.py:2917) выставляется в **реальный** момент окончания I2S DMA (с точностью до network latency + ~ring drain). Это значит discard window отсчитывается от реального конца звука. **Если duration_sec неверен** (например, prepared WAV содержит trailing silence, или ESP буферизует больше) — discard window сдвинется и self-echo может протечь.

**How to verify in Wave 6:** Включить `trace_post_tts_lag: true` в `tuning.diagnostics` (см. Config.schema.json:1156-1158 — описание про `mic_lag_diag_chunk` event), прогнать 10 turn-ов, сравнить временные метки `tts_finished` и `mic_unmuted` с RMS envelope из `mic_lag_diag_chunk`. Если RMS env still high на момент `mic_unmuted` — увеличить либо Jetson sleep, либо discard window.

### Pitfall 6: `post_tts_discard_window_ms=2500` — physical proximity effect

Текущее значение 2500 мс настроено для **HDMI динамиков в стенде** (на расстоянии метров от микрофона). Phase 29 переносит звук в корпус, где динамик и мик разделены **сантиметрами** через корпус. Гипотезы:

| Сценарий | Effect на required discard window |
|----------|-----------------------------------|
| Direct path (динамик → мик через воздух): короче на ~3-5 мс | пренебрежимо |
| Body conduction (динамик → корпус → мик через корпус): добавляет ~10-30 мс resonance tail | +30 ms если корпус резонирует |
| Reverb в маленьком корпусе (стоячие волны): добавляет 100-500 мс tail | критично |
| ESP I2S DMA latency: уже учтён в `duration_sec` sleep, не должен меняться | 0 |

**Recommendation для планнера:** Не менять 2500 ms превентивно. Wave 6 запускает 10 turn-ов с дефолтом, измеряет фактические violations через snippet выше. Если 0 violations — оставить. Если 1-3 violations — поднять до 3000. Если >3 — диагноз через `trace_post_tts_lag`.

### Pitfall 7: LC-фильтр питания — BOM на случай Wave 1 revisit

Если Wave 3 (C3) покажет шум от моторов, добавить между step-down (5V output) и PAM8403 VDD:

```
step-down 5V ──[L = 22 µH радиальный дроссель, >0.5A]──┬── PAM8403 VDD
                                                       │
                                                  [C = 470 µF 10V electrolytic]
                                                       │
                                                      GND
```

BOM addition: 1× дроссель 22 µH 0.5A (Würth 7447480221 или аналог), 1× электролит 470 µF 10V 105°C. Cutoff = 1/(2π√LC) ≈ 50 Hz — фильтрует всё выше, оставляет питание чистым. Это revisit-only, не делать сразу.

---

## Wave Structure Critique

CONTEXT.md proposes:
- Wave 1: hardware (пайка + омметр) → Wave 2: cap (schema + Config.json) → Wave 3: loopback → Wave 4: flip → Wave 5: ramp → Wave 6: self-echo → Wave 7: docs

### Critique

**Issue 1: Wave 2 должен идти ДО Wave 1.**

CONTEXT.md ставит Wave 2 (Config schema cap до 1.0, starter volume = 0.5) после Wave 1 (пайка). Это безопасно, но **не оптимально**: если в процессе пайки оператор случайно перезагрузит orchestrator (например, для проверки другого фикса), Config.json всё ещё имеет `tuning.voice.volume = 1.1` (текущее значение) и схема позволяет 2.0. Лучше:

- **Wave 0 / Pre-flight (новый):** Config.json `tuning.voice.volume = 1.1 → 0.5` **И** Config.schema.json `maximum: 2.0 → 1.0`. Pydantic-clamp проверка. Закоммитить. Это безопасно для текущего HDMI-маршрута (с volume=0.5 Адам будет тише на HDMI — оператор должен знать).
- **Wave 1:** hardware пайка + омметр (без изменений)
- **Wave 2 (был):** удалить — слилось с Wave 0
- **Wave 3-7:** как было

**Issue 2: Wave 4 (flip output_target) и Wave 5 (ramp) можно объединить.**

После flip Адам молчит уже на корпусе. Первый же live turn в Wave 4 — это уже первая итерация ramp с volume=0.5. Делать отдельную Wave 5 имеет смысл только если в Wave 4 ловим что-то критичное (например, тишина). Предложение: **Wave 4 = flip + первый live turn (volume=0.5) + первое subjective evaluation**. Если PASS — продолжать в той же волне ramp до 1.0. Это сжимает 2 волны в 1 и убирает излишнюю церемонию.

**Issue 3: Wave 6 self-echo долгий, не должен блокировать docs.**

CONTEXT.md ставит Wave 7 (docs) после Wave 6 (self-echo). Но Wave 6 — это **30+ мин прогон** + анализ events.jsonl. Docs (Wave 7) можно начинать **в параллель** с Wave 6, потому что docs не зависит от данных Wave 6 — структура RUNBOOK section известна заранее, только конкретное число `post_tts_discard_window_ms` может уточниться. Предложение: **Wave 6 и Wave 7 параллельны** (Wave 7 финализирует final discard_window number когда Wave 6 закончит).

### Parallelisation safety table

| Wave pair | Can parallelize? | Reason |
|-----------|------------------|--------|
| Wave 0 (Config) ↔ Wave 1 (hardware) | NO | Wave 0 — гейт безопасности перед физической работой |
| Wave 1 (hardware) ↔ Wave 3 (loopback) | NO | Wave 3 требует собранного железа |
| Wave 3 (loopback) ↔ Wave 4 (flip) | NO | Wave 4 переключает production-маршрут, требует Wave 3 PASS |
| Wave 4-5 объединены | ✓ | Логически одна задача: первый live + calibration |
| Wave 6 (self-echo) ↔ Wave 7 (docs) | YES | Docs не зависит от Wave 6 results кроме одного числа |

### Recommended wave structure для PLAN.md

```
Wave 0 (Pre-flight, code-only): Config.schema.json cap 2.0→1.0 + Config.json volume 1.1→0.5
Wave 1 (Hardware):  пайка + 4 омметровых проверки (C1) + power-on test (C2)
Wave 2 (Loopback):  generate test WAV, curl POST :81/speaker, slow ramp в 440Hz/1kHz/voice clip
Wave 3 (Flip + Calibration): output_target → esp32_speaker, restart, live turn @0.5, ramp 0.5→0.7→0.85→1.0 (C4, C5)
Wave 4 (Stability): 30-мин thermal run (C6) — параллельно Wave 5
Wave 5 (Self-echo): 10 turn-ов, events.jsonl assertion (C7, C8) — параллельно Wave 4
Wave 6 (Docs):      RUNBOOK section + commit (C9, и финализация C10)
```

(7 → 6 волн, с понятной зависимостью и параллельными хвостами.)

---

## Smoke-Test Artifacts

### Test WAV для Wave 2 (loopback)

**Specification:**
- Format: PCM, 16-bit, mono, 44100 Hz (precisely matching `ESP32_SPEAKER_SAMPLE_RATE` constant)
- Frequency: 440 Hz (concert A, легко распознаваемая, безопасная для динамиков)
- Duration: 1.0 second (достаточно для слухового анализа, не overflows ring buffer; ring = `kSpeakerRingBufferBytes` ≈ десятки KB)
- Amplitude: -12 dBFS (rms ≈ 0.25 * full scale) — даёт headroom при tuning.voice.volume=1.0, не клиппит при тестах с volume>0
- Storage: `tests/fixtures/test_440hz_1s_-12dbfs.wav`

**Generation (sox available, ffmpeg not):**

```bash
mkdir -p tests/fixtures
sox -n -r 44100 -c 1 -b 16 tests/fixtures/test_440hz_1s_-12dbfs.wav synth 1 sine 440 vol -12dB
# Verify:
sox --info tests/fixtures/test_440hz_1s_-12dbfs.wav
# expected: Channels: 1 / Sample Rate: 44100 / Precision: 16-bit / Duration: 00:00:01.00
```

**Negative test WAV (Wave 2, C3 fail-path validation):**

```bash
# Wrong sample rate — expected HTTP 400 "speaker_wav_format_mismatch"
sox -n -r 48000 -c 1 -b 16 tests/fixtures/test_negative_48000hz.wav synth 1 sine 440 vol -12dB

# Wrong channels — same expected 400
sox -n -r 44100 -c 2 -b 16 tests/fixtures/test_negative_stereo.wav synth 1 sine 440 vol -12dB
```

**Voice-realistic WAV (optional, для Wave 3):**

```bash
# 2-second "voice-like" sweep (имитирует range русской речи)
sox -n -r 44100 -c 1 -b 16 tests/fixtures/test_voice_sweep.wav synth 2 sine 200-2000 vol -12dB
```

### Curl commands (для PLAN.md task descriptions)

```bash
# C3 positive
curl -v --noproxy '*' -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @tests/fixtures/test_440hz_1s_-12dbfs.wav \
  http://192.168.0.171:81/speaker
# expect HTTP 200 {"status":"ok"}

# C3 negative (sample rate)
curl -v --noproxy '*' -X POST \
  -H "Content-Type: audio/wav" \
  --data-binary @tests/fixtures/test_negative_48000hz.wav \
  http://192.168.0.171:81/speaker
# expect HTTP 400 {"error":"speaker_wav_format_mismatch"}

# ESP speaker readiness probe (Wave 1, after firmware boot)
curl --noproxy '*' -fsS http://192.168.0.171/api/status | jq '.speaker_ready,.speaker_buffer_fill,.speaker_underruns'
# expect: true, 0, 0
```

### Storage decision

`tests/fixtures/` — да, не `data/sounds/`:
- `data/sounds/` — production cue (`success.wav`, `boot.wav`), не должен мусориться test-данными
- `tests/fixtures/` уже подразумевается project structure (раздел Agent Behavior Rules CLAUDE.md: «тесты модуля → `tests/inference/`»)
- Test WAV должен быть в git, чтобы воспроизводить acceptance test через 3 месяца (sox команда rebuilds detrministic, но коммит надёжнее)

---

## Code Citation Index

> file:line ссылки для PLAN.md — копировать в task descriptions буквально.

### Software entry points

| Path | Lines | Purpose |
|------|-------|---------|
| `System/adam/inference.py` | 20 | `_NO_PROXY_OPENER` definition (bypass v2ray) |
| `System/adam/inference.py` | 26-28 | `ESP32_SPEAKER_SAMPLE_RATE/CHANNELS/BITS` constants (44100/1/16) |
| `System/adam/inference.py` | 31-39 | `_build_wav_header()` — minimal 44-byte WAV |
| `System/adam/inference.py` | 42-72 | `_parse_wav()` — chunk walker |
| `System/adam/inference.py` | 75-92 | `_prepare_wav_for_esp32_speaker()` — entry point для Phase 29 maintenance |
| `System/adam/inference.py` | 204 | `_VALID_TTS_OUTPUT_TARGETS = ("jetson_hdmi", "esp32_speaker")` |
| `System/adam/inference.py` | 213-224 | `output_target` validation в `TTSClient.__init__` (читается ОДИН раз при старте) |
| `System/adam/inference.py` | 226-227 | `_mcu_speaker_url` setup |
| `System/adam/inference.py` | 274-278 | `_play_wav_bytes_sync()` routing switch |
| `System/adam/inference.py` | 348-404 | `_play_wav_bytes_to_esp32_sync()` — POST + duration sleep |
| `System/adam/inference.py` | 396-399 | Duration-sync sleep (alignment "TTS finished" with reality) |
| `System/adam/inference.py` | 406-413 | `interrupt_playback` barge-in comment block (deferred limitation) |
| `System/adam/inference.py` | 426-430 | `tts_barge_in_unsupported` event emit |

### Orchestrator (TTS flow + volume + mute)

| Path | Lines | Purpose |
|------|-------|---------|
| `System/Orchestrator.py` | 122 | `runtime_state["last_tts_finished_at"]` init |
| `System/Orchestrator.py` | 147-169 | `_apply_wav_speed()` |
| `System/Orchestrator.py` | 172-end | `_apply_wav_volume()` — software gain |
| `System/Orchestrator.py` | 387 | `self._post_tts_discard_window_ms` init |
| `System/Orchestrator.py` | 826-833 | discard-window activation logic |
| `System/Orchestrator.py` | 979 | `mic_muted` event emit (reason: asr_transcribing) |
| `System/Orchestrator.py` | 997, 1020-1055 | `mic_unmuted` + post-TTS guard window |
| `System/Orchestrator.py` | 2684-2688 | `_current_volume()` (hot-reload per chunk) |
| `System/Orchestrator.py` | 2793, 2844 | `_apply_wav_volume(wav, _current_volume())` call sites |
| `System/Orchestrator.py` | 2831 | `tts._play_wav_bytes_sync(pending_wav)` final chunk |
| `System/Orchestrator.py` | 2856, 2884 | mid-stream `tts._play_wav_bytes_sync` calls |
| `System/Orchestrator.py` | 2859-2865 | esp32_speaker-specific failure handling (`tts_chunk_failed`) |
| `System/Orchestrator.py` | 2917 | `last_tts_finished_at = time.perf_counter()` |
| `System/Orchestrator.py` | 2939 | **CRITICAL for C7:** `event_log.append("tts_finished", {"ok": ok, "degraded":...})` — здесь добавить `"target": tts.output_target` |
| `System/Orchestrator.py` | 2945, 2950 | `tts_started`/`tts_finished` в `_speak()` (alternative path) |
| `System/Orchestrator.py` | 3268-3269 | runtime `post_tts_discard_window_ms` reload |

### Firmware (ESP32)

| Path | Lines | Purpose |
|------|-------|---------|
| `Subsystem/AdamsServer/config/PinsConfig.h` | 38-44 | I2S DAC pins: BCLK=38, LRCK=39, DATA=40, MCLK→GND |
| `Subsystem/AdamsServer/config/AdamsConfig.h` | 94 | `kSpeakerSampleRate = 44100` |
| `Subsystem/AdamsServer/src/audio/AudioModule.cpp` | 88 | `kSpeakerPlaybackPort = I2S_NUM_1` |
| `Subsystem/AdamsServer/src/audio/AudioModule.cpp` | 342-386 | `initSpeakerStdTxChannel()` — Philips 16-bit stereo, slot_mask=BOTH (mono → L=R) |
| `Subsystem/AdamsServer/src/audio/AudioModule.cpp` | 714-756 | `initSpeakerPlayback()` — ring alloc + task pin to APP_CPU_NUM |
| `Subsystem/AdamsServer/src/web/WebServerModule.cpp` | 2529-2603 | `speakerHandler()` — `/speaker` HTTP endpoint |
| `Subsystem/AdamsServer/src/web/WebServerModule.cpp` | 2533-2535 | 503 if `!speakerReady` |
| `Subsystem/AdamsServer/src/web/WebServerModule.cpp` | 2569-2574 | **Strict header validation** — audioFormat≠1 OR channels≠1 OR sampleRate≠44100 OR bits≠16 → HTTP 400 `speaker_wav_format_mismatch` |
| `Subsystem/AdamsServer/src/web/WebServerModule.cpp` | 2582-2592 | Pacing: 4 ms vTaskDelay if ring full |

### Config

| Path | Lines | Purpose |
|------|-------|---------|
| `System/Config.json` | (services.tts.output_target) | currently `"jetson_hdmi"` — Wave 3 flip |
| `System/Config.json` | (tuning.voice.volume) | currently `1.1` — Wave 0 set to `0.5` |
| `System/Config.schema.json` | 947 | **EDIT:** `"maximum": 2.0` → `"maximum": 1.0`; обновить description |
| `System/adam/tuning.py` | (volume field) | Pydantic-model — проверить, нет ли захардкоженного le=2.0; обновить если есть |

### Runbook insertion point

| Path | Lines | Purpose |
|------|-------|---------|
| `docs/RUNBOOK_JETSON_EXHIBITION.md` | 88 (after `## Media Policy`), 96 (before `## TTS Dependencies`) | **Insert new section `## Audio Output Path (ESP32 Speaker)` here.** |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `sox` | Test WAV generation (Wave 2) | ✓ | (verified) | — |
| `ffmpeg` | (would be alt for WAV gen) | ✗ | — | use `sox` |
| `curl` | All HTTP probes | ✓ (system) | — | — |
| `jq` | events.jsonl parsing in verify scripts | (assume yes — стандарт для Adam-Chip workflows) | — | use `python3 -c 'import json; …'` |
| `python3 wave` module | WAV generation alternative | ✓ | — | — |
| PlatformIO (pio) | Firmware rebuild (если будет нужен) | unknown on Jetson | — | OTA через `tools/flash_ota.ps1` с Windows |
| Multimeter | Wave 1 omметровые проверки | physical, у оператора | — | — |
| Oscilloscope | Wave 1 power-spike test (C2) | optional | — | слух + headphone on speaker output |

**No blocking dependencies.** `ffmpeg` отсутствует, но `sox` покрывает все нужды.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Event name в Wave 6 C7 — это `tts_finished`, не `tts_played` (CONTEXT.md typo) | Validation C4, C7 | Acceptance criterion проверяется не на тот event → false PASS |
| A2 | `target` field в `tts_finished` payload **отсутствует** в текущем коде; нужно добавить в `Orchestrator.py:2939` чтобы C7 был measurable | Validation C7 | Без правки кода критерий `target=esp32_speaker` неверифицируем |
| A3 | Pydantic-модель `voice.volume` в `tuning.py` может иметь захардкоженный `le=2.0` — обновлять заодно со schema | Validation C10, Code Citation Index | Если есть и не обновлён — schema-only change не enforced runtime |
| A4 | XSMT pin PCM5102A на breakout-module **может быть** доступен (зависит от конкретной модели); если нет — workaround через MOSFET-switch deferred | Integration Pitfalls #1 | Boot pop возможен; minor (раздражение, не damage) |
| A5 | Динамики 2209 (4 шт × 1W 8Ω) — это user-provided; rating 1W RMS — assumed из CONTEXT.md спека, datasheet самих динамиков не проверен | Validation C5, C6 | Если real rating <1W → thermal failure в C6 |

**Risk profile:** Все ассумпции либо verifiable за <5 минут в Wave 0/1, либо low-impact. Никаких блокирующих unknowns.

---

## Open Questions

1. **Event name fix in Orchestrator.py:2939 — кто это делает?**
   - Этот RESEARCH рекомендует добавить `"target": tts.output_target` в `tts_finished` payload. Это маленькое code-change, но Phase 29 описана в CONTEXT.md как «software flip без новых модулей». Планнер должен решить: (a) добавить task в Wave 4 («augment tts_finished event с target»), (b) использовать существующий `tts_chunk_failed.target` field для negative-case + assume positive cases (нет `tts_chunk_failed` за окно = все chunk'и `target=esp32_speaker`). Вариант (a) cleaner; вариант (b) cheaper.

2. **Pydantic-validation для `voice.volume.maximum=1.0` enforced runtime?**
   - Нужно проверить `System/adam/tuning.py` для `volume: float = Field(0.5, ge=0.0, le=2.0)` или подобного. Если есть `le=2.0` — заодно опустить до 1.0 в Wave 0.

3. **XSMT pin доступность на конкретном PCM5102A модуле**
   - Не известно без визуальной инспекции модуля. Если pin не выведен — boot pop проблема живёт; mitigation deferred.

---

## Sources

### Primary (HIGH confidence)
- `System/adam/inference.py:1-431` — [VERIFIED: read in this session]
- `System/Orchestrator.py:122, 147-200, 387, 826-833, 979, 997-1055, 2684-2688, 2825-2960` — [VERIFIED: read in this session]
- `Subsystem/AdamsServer/src/web/WebServerModule.cpp:2529-2603` — [VERIFIED: read in this session]
- `Subsystem/AdamsServer/src/audio/AudioModule.cpp:88, 342-386, 714-756` — [VERIFIED: read in this session]
- `Subsystem/AdamsServer/config/PinsConfig.h:38-44` — [VERIFIED]
- `Subsystem/AdamsServer/config/AdamsConfig.h:94` — [VERIFIED]
- `System/Config.schema.json:941-948` — [VERIFIED]
- `docs/RUNBOOK_JETSON_EXHIBITION.md` structure — [VERIFIED: grep output line 1-165]
- `29-CONTEXT.md`, `29-DISCUSSION-LOG.md` — [VERIFIED]
- `sox` availability — [VERIFIED: bash check]

### Secondary (MEDIUM confidence)
- PAM8403 datasheet behavior under 4Ω at 5V — [CITED: Diodes DS36439 Rev 1.3 (via CONTEXT.md)]
- PCM5102A line-out 2.1 Vrms, internal soft-mute, XSMT pin existence — [CITED: TI datasheet (via CONTEXT.md)]

### Tertiary (LOW confidence)
- Динамики 2209 точный rating — [ASSUMED — user-provided in CONTEXT.md]
- Boot-pop magnitude PCM5102A — [ASSUMED — общая характеристика I2S DAC семейства, конкретно для этого модуля не измерено]

---

## Metadata

**Confidence breakdown:**
- Validation Architecture: HIGH — все 8 criteria измеримы конкретными командами по коду, который существует
- Integration Pitfalls: HIGH для #2, #3, #4, #5 (codebase-verified); MEDIUM для #1, #7 (hardware-зависимые); HIGH для #6 (метод valid, числа empirical)
- Wave Structure Critique: HIGH — основано на анализе зависимостей между waves
- Smoke-Test Artifacts: HIGH — `sox` команды проверены synthetically
- Code Citation Index: HIGH — все file:line проверены чтением

**Research date:** 2026-05-18
**Valid until:** Until Phase 29 closes (no upstream code drift expected — Phase 29 is the last consumer of `_play_wav_bytes_to_esp32_sync` paths as currently coded).

## RESEARCH COMPLETE

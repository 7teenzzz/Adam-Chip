# Phase 41: Audio Pipeline Latency Fix — Context

**Gathered:** 2026-06-12 (Debugger-mode session, branch `SmartFlora` — out-of-scope diagnosis, see Branch gap note below)
**Status:** Diagnosis complete, ready for `/gsd-plan-phase 41`

**Note:** изначально диагностика была подготовлена как "Phase 37", но номер 37 уже занят в ROADMAP.md (VisitorRegistry + Notes System, ветка `subconscious-symbiont`). Переименовано в Phase 41 (следующий свободный номер после Phase 40) во избежание коллизии.

<domain>
## Phase Boundary

Пользователь сообщил «OWW (адам.onnx) не детектит ничего» — пробуждение по слову «адам» перестало срабатывать. Полная диагностика тракта аудио (mic → LocalMicReader → InputDSP → VAD/OWW/ASR) выявила **корневую причину уровнем ниже Python**: PipeWire отдаёт аудио с USB-микрофона WebCamera пачками раз в ~1.1с вместо непрерывного потока 20мс-кадров (~50 Гц), что ломает OWW, VAD-endpointing и ASR-таймауты одновременно.

**В рамках фазы:**
1. Зафиксировать и проверить системный фикс PipeWire/WirePlumber (latency узла WebCamera)
2. Исправить `_find_pulse_source` race condition (intermittent `pulse_source: None`)
3. Пересчитать калибровку OWW (`threshold`/`debounce_hits`) и VAD/ASR endpointing-таймеров ПОСЛЕ восстановления нормального темпа кадров
4. Решить судьбу сегодняшнего uncommitted фикса `_raw_chunk_for_monitor` (OWW на pre-DSP аудио) — оставить/откатить/доработать
5. Живая верификация: «адам» триггерит wake_word_detected при нормальной нагрузке

**Out of scope:**
- SmartFlora-функциональность текущей ветки (`flora.user_presets`, sequences, emotion_map) — не трогать, это отдельная фаза 36B
- Полная миграция PulseAudio→PipeWire (Phase 32, stub, отдельная задача) — PipeWire уже используется (`pactl` подтверждает `PipeWire` backend), фикс здесь — точечный override latency для одного устройства, не миграция

**Branch gap:** текущая ветка `SmartFlora` (см. BRANCH.md) посвящена технофлоре, а не аудио. Этот фикс логически принадлежит другой ветке (например, назад на `subconscious-symbiont`/`main` или новой `audio-pipeline-fix`). Решение о ветке — на этапе `/gsd-plan-phase` или перед `/commit-push`.

</domain>

<findings>
## Диагностика — полная цепь находок (2026-06-12)

### 🔴 ГЛАВНАЯ НАХОДКА (подтверждена живыми замерами и прямым тестом arecord)

**PipeWire ALSA-узел `alsa_input.usb-WebCamera_WebCamera_202509021958-02.mono-fallback` доставляет аудио пачками ~120мс раз в ~1.1-1.2с вместо непрерывных 20мс-кадров (~50 Гц).**

Замер 1 — живые события `oww_score`/`audio_level` за 12с (текущая активная сессия voice_loop, PID 335784, корректный `pulse_source`):
```
oww_score: 18 событий за 12с, приходят парами/тройками с интервалом ~1.1-1.2с
audio_level: 7 событий за 12с (ожидалось ~300 при 25 Гц cadence)
```

Замер 2 — прямой `arecord -D pulse -f S16_LE -r 16000 -c 1 -t raw` с тем же `PULSE_SOURCE`:
```
read 640 bytes at t=1.053  ×6 подряд (мгновенно)   ← 120мс аудио
read 640 bytes at t=2.205  ×4 подряд               ← 80мс аудио
```
То есть в Python попадает **~10-11% от непрерывного потока**, остальное теряется на уровне PipeWire ДО arecord.

Проверены и НЕ помогли:
- `-F 20000 -B 100000` (явный period/buffer 20мс/100мс) — тот же ~10x недобор throughput, только пачки мельче и чаще (~190мс/фрейм)
- `PULSE_LATENCY_MSEC=20` — без изменений

**Корень**, найден через `pw-cli info <node WebCamera Mono>` и `/proc/asound/card0/pcm0c/sub0/hw_params`:
```
node.max-latency = 48000/48000     ← 1 секунда (!), при глобальном clock.quantum=1024 (~21мс)
period_size: 512   buffer_size: 96000   ← buffer = 2 секунды @ 48kHz
```
WirePlumber для этого узла не переопределяет дефолтный (видимо завышенный для USB-аудиокласса) `node.max-latency`, и PipeWire батчит выдачу узла раз в ~1с.

### Импакт на OWW

- `_ww_buf` копит 4×20мс=80мс перед вызовом `process_chunk` — но эти 80мс приходят **раз в ~1.1с**, и являются хвостом 120мс-пачки, а не непрерывным потоком.
- Слово «адам» (~400-600мс произношения) почти всегда либо целиком попадает в «дыру» между пачками, либо размазывается по несвязным фрагментам — мел-спектрограмма модели никогда не видит цельное произношение.
- `debounce_hits=2` требует **двух последовательных** вызовов `process_chunk` со score≥threshold — соседние вызовы разделены ~1.1с реального времени и физически НЕ являются соседними кадрами аудио. Поэтому score стабильно «застывает» на 0.001 (фоновый шум на разрозненных фрагментах).

### Импакт на VAD/ASR (вторично, не было в исходном запросе, но важно)

Все таймеры endpointing калиброваны на 20мс@50Гц:
- `silence_after_speech_ms=1000`, `endpointing_debounce_frames=5`, `endpointing_voiced_debounce_frames=3`, `reply_silence_timeout_sec`, `*_segment_ms` — при фактическом темпе ~1 кадр/1.1с все эти величины растягиваются в wall-clock на порядок. Это вероятно объясняет и другие жалобы на «вялость»/задержки голосового цикла, не только OWW.

### Сегодняшний uncommitted фикс (Orchestrator.py, не решает проблему)

`_ww_buf.append(_raw_chunk_for_monitor)` вместо `_ww_buf.append(chunk)` — гипотеза была «220Hz HPF убивает score OWW». HPF (`audio_input.dsp.hpf.enabled=true, hz=220`, добавлен в `iAdam.json` коммитом `5f71650`) реально применяется к `chunk` (post-DSP), так что фикс технически меняет вход OWW — но проблема на уровне PipeWire, ДО Python, поэтому фикс **не дал эффекта** (score стабильно 0.001 спустя >50 мин работы с этим фиксом). Сам по себе фикс не вреден и потенциально корректен (full-spectrum сигнал для модели), но решение о его сохранении нужно принять ПОСЛЕ того, как PipeWire-фикс восстановит нормальный темп кадров — возможно, тогда выяснится, что HPF и не мешал.

### Историческая хронология деградации (data/adam/events.jsonl, oww_score по дням)

```
2026-06-08: max=0.768 (working)
2026-06-09: max=0.77  (working)
2026-06-10: max=0.005 (DEGRADED)
2026-06-11: max=0.001, unique=1 (STUCK)
2026-06-12: max=0.011 (DEGRADED, today)
```
Регрессия началась между 06-09 и 06-10. Кандидаты-коммиты (audio/Orchestrator/Config, в этом диапазоне): `0c71048` (AIIM merge, 06-09 18:58 — только импорт wake_word, не функциональный), `70f3e47` (VLM/MJPEG, 06-09 20:16), `1c4b045`/`59581bd` (flora). InputDSP сам был подключен к `_vad_loop` ещё 06-08 (`79b07e5`/`772f123`/`cb93798`) и НЕ ломал OWW 06-08/06-09 — значит HPF/InputDSP не первопричина. Точная причина регрессии 06-09→06-10 **не установлена** (вероятно смена `mic_source` на путь через PipeWire/pulse, который всегда имел `node.max-latency=1s`, просто раньше через этот узел звук не шёл) — низкий приоритет, т.к. главный фикс (WirePlumber) решает проблему независимо от истории.

### Побочная находка: `_find_pulse_source` race condition

`System/adam/local_mic_reader.py:_find_pulse_source()` вызывается один раз в `__init__`/`start()`, запускает `pactl list short sources`. На 3 из 7 стартов voice_loop сегодня (09:48, 11:48, 11:53) вернул `None` — PipeWire/USB ещё не готовы при раннем старте сервиса (boot race). Без `PULSE_SOURCE` arecord подключается к default source (может быть не WebCamera). Текущая (рабочая) сессия резолвится корректно — баг proявляется только на холодном старте после ребута.

### Уже применённый шаг (этот сеанс)

Создан `~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua` — user-level override (`node.latency=512/48000`, `api.alsa.period-size=512`, `session.suspend-timeout-seconds=0`) для `alsa_input.usb-WebCamera_*`. **НЕ ПРИМЕНЁН** — требует `systemctl --user restart wireplumber pipewire pipewire-pulse`, что разорвёт текущий live mic-стрим оркестратора (auto-mode classifier заблокировал рестарт как live-disrupting действие, требует явного подтверждения пользователя). LocalMicReader имеет reconnect-loop (`sleep(2.0)` при ошибке) — должен восстановиться сам, но это нужно подтвердить.

</findings>

<decisions>
## Implementation Decisions — для /gsd-plan-phase 41

### Решено в этом сеансе
- WirePlumber override создан в `~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua` (user-level, не `/etc/`, т.к. wireplumber/pipewire — `systemctl --user` сервисы на этой машине)
- Подход: точечный override latency для WebCamera-узла, НЕ полная PipeWire-миграция (Phase 32 остаётся отдельным stub)

### Открытые вопросы для планирования
1. **Активация WirePlumber-фикса**: рестарт `wireplumber`/`pipewire`/`pipewire-pulse` оборвёт live mic — нужен явный шаг с подтверждением и проверкой recovery LocalMicReader (reconnect-loop)
2. **Верификация фикса**: повторить замер (12с tail `oww_score`/`audio_level`, ожидаем ~150 событий oww_score за 12с при нормальном темпе ~12.5Гц) + live-тест произнесения «адам»
3. **Калибровка OWW после фикса**: `threshold=0.01`/`debounce_hits=2` подбирались под «голодный» поток (никогда давали стабильно высокий score) — после восстановления темпа, возможно, нужно вернуться к историческим значениям (06-09: `threshold≈0.08`, max score 0.77) или перекалибровать заново
4. **Судьба `_raw_chunk_for_monitor` фикса** в Orchestrator.py — оставить (raw audio для OWW технически корректнее) или откатить к post-DSP `chunk`, решить ПОСЛЕ верификации п.2
5. **`_find_pulse_source` retry**: добавить retry-with-backoff (несколько попыток `pactl list short sources` с интервалом) ИЛИ fallback на последний известный source name из `events.jsonl`/конфига
6. **Branch**: текущая работа на `SmartFlora` (flora-фокус) — нужно решить, коммитить ли аудио-фикс отдельно/на другую ветку перед `/commit-push`

</decisions>

<canonical_refs>
## Файлы

- `~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua` — НОВЫЙ, создан, не активирован (вне репозитория, `~/.config/`)
- `System/Orchestrator.py` — `_vad_loop` (~1174-1488): `_raw_chunk_for_monitor`/`chunk`/`_ww_buf`/`_input_dsp.process()`, OWW scoring (~1349-1372)
- `System/adam/local_mic_reader.py` — `_find_pulse_source()` (147-160), `_open_drain_reconnect_loop` (reconnect на ошибку, sleep 2.0)
- `System/adam/wake_word.py` — `OpenWakeWordEngine` (debounce, threshold, reset)
- `System/adam/audio_dsp.py` — `InputDSP` (HPF 220Hz применяется к post-DSP `chunk`)
- `System/Config.json` — `wake_word.{threshold=0.01, debounce_hits=2, vad_threshold=0}`, `media.audio.{frame_ms=20, sample_rate=16000}`, `services.asr.{silence_after_speech_ms, endpointing_*_debounce_frames, reply_silence_timeout_sec}`
- `Agent-Adam-Chip/iAdam.json` — `audio_input.dsp.hpf={enabled:true, hz:220}` (добавлен 06-10, коммит `5f71650`)
- `data/adam/events.jsonl` — источник всех замеров (`oww_score`, `audio_level`, `local_mic_stream_active`)

## Связанные фазы
- Phase 32 (`32-pipewire-audio-migration`) — stub, полная PulseAudio→PipeWire миграция (НЕ требуется для этого фикса — PipeWire уже активен)
- Phase 31 (`31-audio-input-tuning-panel`) — InputDSP/EQ-панель, источник HPF 220Hz
- `asr-wakeword-fixes/PLAN.md` — исторический план калибровки OWW (threshold/debounce), может содержать релевантный контекст для п.3 решений

</canonical_refs>

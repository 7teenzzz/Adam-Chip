---
phase: 31
plan: 01
type: feature
wave: 1
depends_on: []
files_modified:
  - System/Config.json
  - System/Config.schema.json
  - System/adam/tuning.py
  - System/adam/audio_dsp.py
  - System/Orchestrator.py
  - System/adam/api_runtime.py
  - System/adam/ui.py
  - System/WebUI/
autonomous: false
requirements:
  - REQ-AUDIO-PANEL-EQ
  - REQ-AUDIO-PANEL-PRESETS
  - REQ-AUDIO-PANEL-MONITOR
  - REQ-AUDIO-PANEL-OWW-LINE
  - REQ-AUDIO-PANEL-TOGGLES
  - REQ-AUDIO-PANEL-VOLUME
must_haves:
  truths:
    - "Серверный DSP применяется к захваченному PCM в _vad_loop ДО OWW и ДО накопления ASR-сегмента — один и тот же обработанный буфер идёт в OWW, ASR и монитор (D-01, D-02)"
    - "Мастер-тумблер DSP=off → чистый passthrough (сырой PCM), голосовой цикл работает как до фазы (bypass) (D-04)"
    - "Каждая полоса EQ + HPF + gain-стадия имеет независимый enabled-флаг; выключение одной не ломает остальные (D-04)"
    - "Любая ошибка DSP / невалидный пресет → tract откатывается на сырой PCM, голос НЕ молчит (D-03 fail-safe)"
    - "Существующий 1-pole vad_hpf_hz обобщён в HPF-стадию каскада — двойной фильтрации нет (D-01)"
    - "Пресеты EQ хранятся в System/Config.json, валидируются pydantic в tuning.py; CRUD через API с hot-reload без рестарта (D-05)"
    - "Монитор: WebSocket отдаёт post-EQ сырой PCM 16-bit 16kHz; браузер играет через Web Audio API (D-06)"
    - "Линия на эквалайзере перетаскиванием меняет wake_word.threshold; поверх — живой оверлей текущего OWW-score (D-08)"
    - "Ползунок громкости управляет media.audio.input_gain (Phase 30), значение применяется живо (D-01 Phase 30)"
    - "safety.half_duplex_mute=true не тронут; монитор — прослушка входа, не TTS-выход"
  artifacts:
    - path: "System/adam/audio_dsp.py"
      provides: "InputDSP — biquad-каскад (HPF + параметрические полосы), master/per-stage toggles, fail-safe bypass, hot-reload коэффициентов из Config"
      contains: "class InputDSP"
    - path: "System/Config.schema.json"
      provides: "Документация media.audio.input_dsp (полосы, флаги) + media.audio.eq_presets + active_preset"
      contains: "input_dsp"
    - path: ".planning/phases/31-audio-input-tuning-panel/31-VERIFICATION.md"
      provides: "Лог: bypass-тест, per-stage A/B через тумблеры, монитор слышен в браузере, OWW-линия двигает порог, пресет CRUD round-trip"
      contains: "bypass"
---

<objective>
Построить единую панель настройки входного аудио-тракта с РЕАЛЬНЫМ серверным DSP. Оператор давит паразитные частоты, ставит фильтры под зал, калибрует wake-word, слыша ровно тот сигнал, что слышит модель (WYSIWYG). Все решения зафиксированы в 31-CONTEXT.md (D-01..D-08).

Три волны:
- **Wave 1 (backend core):** Config-схема DSP/пресетов + движок InputDSP, врезанный в точку захвата (_vad_loop) перед OWW/ASR, с мастер- и per-stage-тумблерами и fail-safe bypass.
- **Wave 2 (backend API/stream):** CRUD пресетов с hot-reload + WebSocket PCM-монитор (post-EQ) + поток OWW-score для оверлея линии.
- **Wave 3 (frontend):** панель — ползунок громкости, графический EQ поверх спектр-виджета (Phase 21A), перетаскиваемые полосы, тумблеры, линия порога+score, кнопка монитора (+pre/post), CRUD пресетов в UI.

Границы: вход остаётся local USB (не ESP-mic); конкретные ЗНАЧЕНИЯ фильтров под зал — runtime-тюнинг через готовую панель, не задача сборки; выходной TTS-DSP (Phase 29) не трогаем. autonomous:false — нужен живой аудио/UI-тест человеком.
</objective>

<tasks>

## WAVE 1 — Backend DSP core

### Task 1: Config-схема входного DSP и пресетов (Config-First, D-05)

**Files:** `System/Config.json`, `System/Config.schema.json`, `System/adam/tuning.py`

**read_first:** `31-CONTEXT.md` (D-01,D-04,D-05), `System/adam/tuning.py` (паттерн pydantic-валидации tuning-блока), `System/Config.json` (`media.audio.input_gain`, `vad_hpf_hz`, `spectrum_*`)

1. Добавить в `media.audio` блок `input_dsp`:
   - `enabled` (bool, мастер-тумблер, D-04)
   - `hpf`: `{ enabled, hz }` — обобщает текущий `vad_hpf_hz` (D-01); пометить старый ключ как legacy-алиас в схеме
   - `bands`: массив параметрических полос, каждая `{ enabled, type (peaking|lowshelf|highshelf|lowpass|highpass), freq_hz, gain_db, q }`
   - `monitor`: `{ tap: "post_eq"|"pre_eq" }` (D-07, дефолт post_eq)
2. Добавить `media.audio.eq_presets`: массив `{ name, hpf, bands }` + `media.audio.active_preset` (string|null — ссылка на имя).
3. В `tuning.py` — pydantic-модели `InputDspBand`, `InputDsp`, `EqPreset` с валидацией (freq в пределах Nyquist 8000, q>0, type из enum). Невалидный пресет → ошибка валидации (ловится в Task 2 fail-safe).
4. Документировать каждый параметр в `Config.schema.json`.

**Verify:**
```bash
python3 -c "import json;json.load(open('System/Config.json'));json.load(open('System/Config.schema.json'));print('JSON ok')"
PYTHONPATH=System python3 -c "from adam.tuning import InputDsp; print('pydantic ok')"
```

### Task 2: Движок InputDSP + врезка в точку захвата (D-01,D-02,D-03,D-04)

**Files:** `System/adam/audio_dsp.py` (NEW), `System/Orchestrator.py`

**read_first:** `System/Orchestrator.py` (`_vad_loop`, `_apply_vad_hpf`, `_ww_buf`, OWW feed, ASR-сегмент аккумулятор), `31-CONTEXT.md` (D-01..D-04)

1. Создать `audio_dsp.py` с классом `InputDSP`:
   - конструктор берёт config-блок `input_dsp`, считает biquad-коэффициенты (scipy `butter`/`iirpeak`/RBJ) для HPF + каждой включённой полосы; хранит состояние фильтров (sos zi) для непрерывности между фреймами.
   - `process(frame_int16) -> int16`: если `enabled=False` → вернуть вход без изменений (мастер bypass). Иначе применить включённые стадии последовательно. Per-stage `enabled=False` → стадия пропускается.
   - `reload(config_block)`: пересчитать коэффициенты на hot-reload (вызывается при изменении Config).
   - **fail-safe (D-03):** весь `process` обёрнут в try/except → при любой ошибке вернуть исходный фрейм + лог WARN один раз (не флудить).
2. В `_vad_loop`: заменить прямой вызов `_apply_vad_hpf` на `InputDSP.process`. Обработанный фрейм идёт И в `_ww_buf` (OWW), И в ASR-сегмент аккумулятор, И (Wave 2) в монитор-очередь — ОДИН буфер (D-02).
3. Инстанс `InputDSP` живёт в оркестраторе, `reload()` на config-change (тот же механизм, что hot-reload tuning).
4. Legacy `_apply_vad_hpf` оставить как fallback, если `input_dsp` отсутствует в конфиге (старые Config.json).

**Verify:**
```bash
# юнит: bypass возвращает вход бит-в-бит; включённый HPF режет НЧ
PYTHONPATH=System python3 -c "
from adam.audio_dsp import InputDSP
import numpy as np
dsp=InputDSP({'enabled':False,'hpf':{'enabled':True,'hz':220},'bands':[]})
x=(np.random.randn(320)*1000).astype('int16')
assert (dsp.process(x.tobytes() if hasattr(dsp,'_bytes') else x)==x).all(), 'bypass not bit-exact'
print('bypass bit-exact ok')
"
# fail-safe: битый конфиг не роняет голос (process отдаёт вход)
```
Живой: рестарт оркестратора, `/api/agent/gate` зелёный, wake «адам» срабатывает при `input_dsp.enabled=true` с дефолтными полосами.

## WAVE 2 — Backend API + стрим

### Task 3: CRUD пресетов EQ с hot-reload (D-05)

**Files:** `System/adam/api_runtime.py`

**read_first:** `System/adam/api_runtime.py` (config R/W, hot-reload механизм, `/api/tuning`/`/api/config`), Task 1 модели

1. Эндпоинты: `GET /api/audio/presets` (список), `POST /api/audio/presets` (создать), `PUT /api/audio/presets/{name}` (редакт), `DELETE /api/audio/presets/{name}`, `POST /api/audio/presets/{name}/activate` (выставить `active_preset` + применить в `input_dsp`).
2. Запись идёт в Config.json через существующий config-writer → hot-reload → `InputDSP.reload()`. Валидация pydantic (Task 1) перед записью; невалидное → 400, конфиг не трогается.
3. Активация пресета копирует его `hpf`/`bands` в живой `input_dsp` (или хранит ссылку — выбрать консистентно с hot-reload).

**Verify:**
```bash
curl -s -XPOST localhost:8080/api/audio/presets -H 'Content-Type: application/json' -d '{"name":"test","hpf":{"enabled":true,"hz":120},"bands":[]}' | python3 -m json.tool
curl -s localhost:8080/api/audio/presets | python3 -m json.tool   # test присутствует
curl -s -XPOST localhost:8080/api/audio/presets/test/activate      # active_preset=test, hot-reload
curl -s -XDELETE localhost:8080/api/audio/presets/test             # round-trip удаление
```

### Task 4: WebSocket PCM-монитор (post-EQ) + поток OWW-score (D-06,D-08)

**Files:** `System/adam/api_runtime.py`, `System/Orchestrator.py`

**read_first:** `31-CONTEXT.md` (D-06,D-07,D-08), `System/Orchestrator.py` (OWW `last_score`), `System/adam/api_runtime.py` (SSE-инфраструктура)

1. WS-эндпоинт `/api/audio/monitor`: при подключении подписывается на очередь обработанных фреймов из `_vad_loop` (post-EQ, D-02), шлёт сырой PCM 16-bit 16kHz. Backpressure: при медленном клиенте дропать старые фреймы (ring), не копить память. Тумблер `monitor.tap` pre/post (D-07) переключает источник.
2. OWW-score для оверлея линии: переиспользовать существующий SSE `/api/events` (тип `audio_level`/добавить `oww_score`) ИЛИ лёгкий тик в WS — отдавать текущий `wake_engine.last_score` и `wake_word.threshold`.
3. half_duplex_mute не трогать: во время TTS монитор может отдавать тишину/паузу — это прослушка входа.

**Verify:**
```bash
# подключиться wscat/скриптом к ws://localhost:8080/api/audio/monitor, получить непрерывный поток байт ~32 КБ/с
python3 scripts/diag_ws_monitor.py --seconds 3   # (создать мини-проверку: считает байты/сек ≈ 32000)
```
Живой: в браузере кнопка «слушать» воспроизводит голос с задержкой < 0.5 c.

## WAVE 3 — Frontend панель

### Task 5: Панель: громкость + графический EQ + тумблеры (D-01,D-04, 2.1.1/2.1.2)

**Files:** `System/adam/ui.py`, `System/WebUI/`

**read_first:** `System/WebUI/` (spectrum-виджет Phase 21A — визуальная база), `System/adam/ui.py`, `media.audio.spectrum_*`

1. Раздел «Аудио-вход» в операторском UI.
2. Ползунок громкости → `media.audio.input_gain` через `/api/config` (живо).
3. Графический EQ: canvas/svg поверх существующего FFT-спектра; перетаскиваемые точки-полосы (freq×gain, Q колесом/жестом) → пишут `input_dsp.bands` через API.
4. Тумблеры: мастер DSP (D-04) + чекбокс на каждой полосе/HPF/gain. Выключенная стадия визуально приглушена, изменения live.

**Verify:** ручной UI-тест: перетаскивание полосы меняет звук в мониторе (Task 4); мастер-тумблер off → звук «сырой».

### Task 6: OWW-линия + score-оверлей + монитор-кнопка + CRUD пресетов в UI (D-06,D-07,D-08, 2.2)

**Files:** `System/WebUI/`

**read_first:** Task 3 (CRUD API), Task 4 (WS монитор + score), `wake_word.threshold`

1. Горизонтальная перетаскиваемая линия на EQ = `wake_word.threshold` (D-08); поверх — живой оверлей OWW-score (из Task 4). Перетаскивание пишет порог через `/api/config`.
2. Кнопка «слушать микрофон»: открывает WS (Task 4), играет PCM через Web Audio API (AudioWorklet). Тумблер pre/post-EQ (D-07).
3. UI пресетов: список + создать/сохранить/переименовать/удалить/активировать (Task 3 API).

**Verify:** ручной: тащу линию — `wake_word.threshold` в Config меняется, реальные срабатывания соотносятся со score; пресет создаётся/активируется/удаляется из UI и переживает рестарт.

### Task 7: Верификация фазы

**Files:** `.planning/phases/31-audio-input-tuning-panel/31-VERIFICATION.md`

1. Зафиксировать: bypass-тест (мастер off = сырой), per-stage A/B через тумблеры, монитор слышен в браузере (post + pre/post toggle), OWW-линия двигает порог с живым score, пресет CRUD round-trip + переживает рестарт, голосовой цикл «адам» стабилен при включённом DSP.

</tasks>

<verification>
Фаза достигнута, когда: оператор из браузера давит паразитную частоту полосой EQ, СЛЫШИТ результат в мониторе (post-EQ), wake «адам» продолжает срабатывать, выключение мастер-тумблера мгновенно возвращает сырой тракт, пресет сохраняется в Config.json и поднимается после рестарта, линия порога с живым OWW-score позволяет откалибровать чувствительность. Все truths из frontmatter выполнены и зафиксированы в 31-VERIFICATION.md.
</verification>

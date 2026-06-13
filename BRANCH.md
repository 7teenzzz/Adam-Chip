# Branch: audio-pipeline-restoration

**Diverged from:** main @ 37830af (merge(ultimate-integration): Phase 35 — live integration complete)
**Goal:** Восстановить аудиотракт захвата (mic capture → OWW/VAD/ASR) на максимальном качестве и со стабильным потоком, используя архитектуру `_run_local`/`arecord` из main (на SmartFlora `local_mic_reader.py` отсутствует здесь — архитектура другая).
**Status:** done — оба merge condition выполнены (см. п.9–10)
**Merge target:** main
**Merge conditions:** OWW/VAD/ASR получают непрерывный поток 16kHz 20ms-фреймов на каденсе ~12.5Hz (oww_score обновляется регулярно, не застывает на ~0.001) — ВЫПОЛНЕНО (12.64Hz, п.9); voice loop проходит полный цикл wake→listen→reply на живом железе — ВЫПОЛНЕНО (подтверждено пользователем, п.10).

**Modified areas:**

- System/Orchestrator.py (`_run_local`, `_start_arecord`, `_capture_device_for`, VoiceLoopController init) — пока не менялось, под исследованием
- System/Config.json (`media.audio.input_device`, `mic_source`) — пока не менялось
- `~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua` (вне git, общесистемный — см. ниже)

**Global changes:** нет на данный момент. Любое изменение `input_device`/`mic_source` в Config.json требует координации с веткой SmartFlora перед мёржем (там используется LocalMicReader с другой логикой).

**Notes for agents:**

Контекст переноса из Phase 41 (ветка SmartFlora, не мёржено):

1. **PipeWire `node.max-latency` проблема (подтверждена, но не единственная причина).**
   PipeWire 0.3.48 ALSA SPA-плагин для карты `alsa_card.usb-WebCamera_*` жёстко
   использует `node.max-latency=48000/48000` (1с) как период IO-таймера, и это НЕ
   переопределяется через WirePlumber `apply_properties` (`node.latency`/`period-size`
   применяются, `node.max-latency` — нет). Результат: PipeWire-стрим с этого устройства
   просыпается ~1 раз/сек и читает ~110ms звука, остальное теряется → OWW/VAD видят
   ~1.3Hz вместо нужных ~12.5Hz.

2. **Текущее состояние системы (вне git, персистентно при смене веток):**
   `~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua` сейчас содержит правило
   `device.disabled=true` для `alsa_card.usb-WebCamera_*` — карта ПОЛНОСТЬЮ исключена
   из PipeWire (pw-dump её не видит, `pactl list sources` тоже). ALSA-устройство
   `/dev/snd/*` карты 0 свободно для прямого доступа (`plughw:0,0` / `hw:0,0`).
   PipeWire/WirePlumber/pipewire-pulse перезапущены и активны. `adam-orchestrator.service`
   остановлен.

   **Конфликт с историческим контекстом этой ветки:** старый BRANCH.md от
   `ultimate-integration` (Phase 35, merge-коммит этой ветки) явно говорит:
   `"input_device" = "pulse" (PipeWire, Phase 32) — НЕ менять на plughw`.
   На main@37830af Config.json действительно `input_device: "pulse"`, и
   `_capture_device_for` пропускает "pulse" как есть → `arecord -D pulse`.
   Но сейчас WebCamera исключена из PipeWire → `arecord -D pulse` НЕ увидит её как
   source. Варианты:
   (a) вернуть карту в PipeWire (откатить `device.disabled=true` в
       `51-webcamera-latency.lua`) — тогда main-архитектура работает как задумана,
       НО возвращается исходная проблема `node.max-latency`;
   (b) временно `input_device: "hw:0,0"` (→ `plughw:0,0`, прямой ALSA, минуя
       PipeWire) — путь не тестировался именно через `arecord` (только через
       `pw-cat`/python-LocalMicReader на SmartFlora).

3. **НЕРЕШЁННАЯ аномалия throughput USB-аудио (КРИТИЧНО, не специфична для ветки).**
   Независимо от метода доступа (PipeWire-pulse, pw-cat, raw ALSA `plughw:0,0`@48kHz,
   raw ALSA `hw:0,0`@16kHz) карта WebCamera отдаёт данные на ~6-11% от заявленной
   sample rate. USB-дескриптор: "Packet Size = 104 bytes", full-speed USB, mono S16LE,
   "Rates: 48000, 24000, 16000, 8000". Гипотеза: USB-аудио интерфейс энумерировался в
   деградированном по bandwidth режиме (связано с более ранним инцидентом
   bus1-port2, решённым через `sudo reboot`). НЕ ПРОВЕРЕНО: сброс/перепрограммирование
   USB-устройства (`usbreset`, sysfs unbind/bind) или повторный `sudo reboot`.
   Если эта аномалия не устранена — никакая конфигурация capture-кода (ни main, ни
   SmartFlora) не даст нужный ~12.5Hz каденс, т.к. источник проблемы — сам поток
   USB-пакетов, а не код/PipeWire-конфиг.

4. **Уже отработанное (не перенесено намеренно):** `stash@{0}` на ветке SmartFlora
   содержит WIP Config.json (`input_device=plughw:0,0`, `camera_capture_interval_sec=0.5`)
   и `local_mic_reader.py` (configurable input_device, `-F` flag, без
   `PULSE_LATENCY_MSEC`).

5. **КРИТИЧЕСКОЕ ОБНОВЛЕНИЕ (2026-06-13 16:52, при попытке шага 5 выше):**
   Во время попытки запустить `arecord -D plughw:0,0 ...` устройство WebCamera
   (USB, bus1-port2) полностью ОТВАЛИЛОСЬ С ШИНЫ и не переэнумерировалось:

   ```text
   usb 1-2: USB disconnect, device number 2
   usb 1-2: device descriptor read/64, error -71  (x4, devices 7-10)
   usb usb1-port2: attempt power cycle
   usb 1-2: device not accepting address 9/10, error -71
   usb usb1-port2: unable to enumerate USB device
   ```

   После этого `/sys/bus/usb/devices/` не содержит `1-2` вообще (только `1-3` —
   Bluetooth), `arecord -l` не видит карту WebCamera, `/proc/asound/cards` показывает
   только HDA + APE. `lsusb -t` показывает bus1 без портов/устройств кроме
   bluetooth.

   Это ТА САМАЯ "bus1-port2 enumeration crisis" из переноса контекста Phase 41 —
   она повторилась и на этот раз НЕ восстановилась сама. USB-аудио throughput
   аномалия (#3 выше) и эта проблема, вероятно, один и тот же деградирующий
   USB-порт/устройство.

   **Это блокер уровня железа/ОС**, не git-ветки. Требуется физический
   переподключение кабеля WebCamera (камера+микрофон на одном USB-устройстве) ИЛИ
   `sudo reboot` (sudo требует пароль, недоступен агенту без интерактивного ввода).
   Никакая работа с capture-кодом на этой ветке не имеет смысла до восстановления
   устройства на шине.

6. **ПОСЛЕ РЕБУТА (2026-06-13 17:00, пользователь сделал `sudo reboot`):**
   USB-устройство WebCamera вернулось на шину чисто: `lsusb -t` показывает
   `Bus 01 Port 2: Dev 4` с интерфейсами Audio×2 + Video×2 (`snd-usb-audio`,
   `uvcvideo`), `arecord -l` видит card 0 WebCamera. Хорошая новость: реэнумерация
   после ребута проходит нормально (throughput-аномалию #3 ещё не пере-измеряли).

   **Найдена ВТОРАЯ, более свежая проблема (наш собственный артефакт из прошлой
   сессии):** правило `device.disabled=true` в `51-webcamera-latency.lua`
   (см. п.2) осталось активным после ребута (файл вне git) и **полностью убрало
   WebCamera из PipeWire**. `pactl list sources` после ребута показывал ТОЛЬКО
   встроенный HDA-вход (`alsa_input.platform-sound.analog-stereo`) — никакого
   WebCamera-источника. Юнит `adam-orchestrator.service` жёстко прибит к
   `PULSE_SOURCE=alsa_input.usb-WebCamera_WebCamera_202509021958-02.mono-fallback`
   (см. `deploy/systemd/adam-orchestrator.service`) — этот источник не существовал,
   `arecord -D pulse` молча падал на ДЕФОЛТНЫЙ pulse-источник (встроенный HDA,
   без реального микрофона). `adam_audio_input_gain.sh` в логах прямо писал:
   `no matching pulse source for 'WebCamera' (pulse down or device absent)`.
   Health-check (`/api/agent/status`) при этом показывал `input_ready: true`
   ("pulse ok") — ложноположительно, т.к. проверяет только открываемость
   устройства `pulse`, не то, ЧТО за источник на самом деле.

   **ИСПРАВЛЕНО:** `51-webcamera-latency.lua` переписан без активных правил
   (история сохранена в комментариях). `systemctl --user restart wireplumber
   pipewire pipewire-pulse` → `pactl list sources` снова показывает
   `alsa_input.usb-WebCamera_WebCamera_202509021958-02.mono-fallback` (RUNNING).
   `sudo systemctl restart adam-orchestrator.service` → лог подтверждает
   `PULSE alsa_input.usb-WebCamera_..._mono-fallback → 105% (default)` — источник
   снова правильный.

   **ОСТАЁТСЯ (исходная Phase 41 проблема, ПОДТВЕРЖДЕНА повторно после фикса
   выше):** `oww_score` события приходят пачками по 2-3 с интервалом ~13ms
   внутри пачки, и ~1.1-1.15s МЕЖДУ пачками — т.е. ~1Hz эффективный каденс
   вместо требуемых ~12.5Hz. `score` стабильно 0.001 (шумовой пол, OWW не видит
   речь). Это в точности node.max-latency=1s артефакт из п.1 — он НЕ устранён,
   просто маскировался проблемой #6 выше (отсутствие источника). Throughput-
   аномалия (п.3, ~6-11%) после ребута + восстановления источника ЕЩЁ НЕ
   пере-измерена.

   **Следующий шаг для Layer-2 (max-latency/каденс):** WirePlumber
   `apply_properties` на уровне device/node не работает (п.1). Неисследованный
   путь — graph-wide `default.clock.quantum` / `default.clock.min-quantum` /
   `default.clock.max-quantum` в `~/.config/pipewire/pipewire.conf.d/*.conf`
   (влияет на IO-таймер ВСЕГО графа PipeWire, а не на per-device alsa_monitor
   rule) — это НЕ то же самое, что `node.max-latency`, и не было опробовано в
   Phase 41.

7. **Attempt 3 (2026-06-13, продолжение) — period-size override применён и
   развёрнут, НО проблема НЕ решена; найдена ИСТИННАЯ корневая причина.**

   Применено правило `alsa_monitor.rules` с matches на `node.name =
   "alsa_input.usb-WebCamera_*"` (а не `device.name`, как в Attempt 1) +
   `apply_properties = { node.latency=512/48000, api.alsa.period-size=512,
   api.alsa.period-num=3, api.alsa.headroom=0 }` —
   см. `~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua`.

   Результат на уровне PipeWire-графа — РЕАЛЬНЫЙ и подтверждённый: `node.max-latency`
   узла сменился с `48000/48000` (1с) на `384/48000` (~8мс), т.е. в ~125 раз. Побочный
   эффект: PipeWire создал RAW-узел `.capture.0.0` вместо `.mono-fallback` (другое
   `node.name`/`object.id`). `deploy/systemd/adam-orchestrator.service` обновлён —
   `PULSE_SOURCE=...capture.0.0`, задеплоен через `adam_install_systemd.sh`
   (whitelisted NOPASSWD), оркестратор перезапущен, `journalctl` подтвердил
   `PULSE ...capture.0.0 → 105% (default)` — источник резолвится правильно.

   **НО: живой каденс `oww_score` в events.jsonl НЕ изменился** — те же пачки
   событий раз в ~1.13-1.15с, `score` стабильно `0.001`. Property-фикс
   `node.max-latency` НЕ влияет на реальную доставку данных в `arecord -D pulse`.

   **Решающий тест (изолирует слой проблемы):** написан минимальный Python-скрипт —
   `arecord -D pulse -f S16_LE -r <rate> -c 1 -t raw` как subprocess, неблокирующее
   чтение через `select`, измерение dt между чанками за 3с, затем `proc.kill()`.
   Результаты (ВСЕ — 2 чанка за 3с, идентичный паттерн):

   | Конфигурация | Размер чанка | dt между чанками | % от номинала |
   | --- | --- | --- | --- |
   | 16kHz, без PULSE_LATENCY_MSEC | 4000 байт (125мс@16kHz) | ~1184 / ~1152мс | ~10.9% |
   | 16kHz, `PULSE_LATENCY_MSEC=20` | 4000 байт | ~1185 / ~1152мс | ~10.9% (без изменений) |
   | 48kHz (нативный, без ресемплинга) | 12000 байт (125мс@48kHz) | ~1192 / ~1152мс | ~8.3% |

   Во ВСЕХ трёх случаях: ровно ~125мс аудио прибывает раз в ~1.15-1.19с —
   независимо от Attempt 3 (PipeWire node-фикс уже применён и активен во время
   этих тестов), независимо от `PULSE_LATENCY_MSEC`, независимо от
   запрошенного sample rate (ресемплинг исключён как причина).

   `/proc/asound/card0/stream0` при этом показывает ALSA-уровень как НОМИНАЛЬНЫЙ:
   `Status: Running`, `Momentary freq = 48000 Hz`, `Packet Size = 104` (корректно
   для full-speed USB Audio @ 48kHz mono 16-bit).

   **ВЫВОД:** Это В ТОЧНОСТИ аномалия #3 (throughput ~6-11% от номинала),
   воспроизведённая САМЫМ МИНИМАЛЬНЫМ возможным путём (`arecord -D pulse`, без
   оркестратора, без какого-либо orchestrator-кода) и подтверждённая ТЕПЕРЬ КАК
   ЕДИНСТВЕННАЯ корневая причина — `node.max-latency=1s` (п.1) был реальной, но
   ВТОРИЧНОЙ проблемой (уже исправлен Attempt 3, без видимого эффекта на конечный
   результат). Аномалия #3 воспроизводится ПОВЕРХ исправленного Attempt 3,
   независимо от PipeWire/Pulse-конфигурации — значит источник проблемы лежит
   НИЖЕ всех протестированных программных слоёв (PipeWire graph node properties,
   pipewire-pulse buffer negotiation, ALSA resampling). Учитывая, что
   `/proc/asound/.../stream0` репортит номинальные 48kHz/104B-packets — это
   расхождение между ЗАЯВЛЕННЫМ instantaneous-rate USB-эндпоинта и РЕАЛЬНО
   доставляемым в userspace объёмом данных, что указывает на
   hardware/firmware-уровень USB-аудио устройства WebCamera (degraded clock /
   некорректная async-feedback синхронизация isochronous endpoint), а НЕ на
   конфигурацию ОС.

   **Дальнейшая работа с capture-кодом/PipeWire-конфигом БЕССМЫСЛЕННА** до
   устранения этой аппаратной аномалии. Непроверенные пути (требуют root или
   физического доступа, недоступны агенту автономно):
   - `sudo usbreset /dev/bus/usb/001/00X` или sysfs unbind/bind
     (`echo '1-2.2' > /sys/bus/usb/drivers/usb/unbind` затем `.../bind`) —
     сброс USB-устройства без полного ребута;
   - физическая переподсоединение кабеля WebCamera в другой USB-порт;
   - повторный `sudo reboot` (после прошлого ребута enumeration прошла чисто,
     но throughput НЕ был пере-измерен сразу — теперь измерен и он СНОВА
     аномальный, т.е. ребут сам по себе НЕ лечит throughput, только
     enumeration).

   **Attempt 3 решение:** оставить как есть (реальное улучшение на уровне
   PipeWire-графа, не вредит, не откатывать) — но он НЕ является решением
   задачи фазы.

8. **`sudo usbreset 32e6:9221` выполнен пользователем (2026-06-13) — НЕ
   ПОМОГ.** Устройство переэнумерировалось чисто (тот же путь `1-2.2`, `Bus 01
   Port 2: Dev 4`, те же дескрипторы Audio×2+Video×2, `/proc/asound/card0/stream0`
   снова "Running, 48000Hz, Packet Size=104"). Throughput-тест (тот же
   Python/arecord -D pulse скрипт, 48kHz и 16kHz) дал **идентичный результат**:
   24000/96000 байт за 3с = **8.3%**, паттерн "125мс аудио раз в ~1.15-1.2с"
   не изменился ни на йоту.

   Это исключает "зависшее USB-состояние"/"stuck endpoint" как причину —
   usbreset полностью переинициализирует USB-протокольный стек устройства, и
   проблема пережила это без изменений. В сочетании с п.3 (raw ALSA hw:0,0 на
   16kHz и 48kHz — тот же результат, тестировано в Phase 41) и п.7 (PipeWire
   graph-фикс + PULSE_LATENCY_MSEC — без эффекта), остаётся практически только
   одна гипотеза: **аппаратный дефект самого USB-аудио кодека/осциллятора
   WebCamera** (внутренний clock работает на ~1/12 от номинальной частоты,
   ИЛИ ADC физически деградировал) — ни ОС, ни драйвер, ни PipeWire это не
   видят как ошибку, потому что USB-протокольный уровень (enumeration,
   descriptors, isochronous packet size) полностью корректен; теряются именно
   аудио-сэмплы внутри устройства до того, как они попадают на USB-шину.

   **ИТОГ (промежуточный):** программные пути исчерпаны (PipeWire-конфиг,
   ALSA напрямую, sample rate, USB-сброс). Остаётся физический вариант —
   другой USB-порт/кабель (не тестировано — все попытки были на порту `1-2.2`).

9. **РЕШЕНО (2026-06-13 18:14) — смена USB-порта устранила корневую причину.**

   Пользователь переподключил кабель WebCamera в другой физический порт.
   Kernel log: `usb 1-2.4: USB disconnect, device number 5` →
   `usb 1-2.4: new HIGH-SPEED USB device number 6 using tegra-xusb`.

   | | До (порт `1-2.2`) | После (порт `1-2.4`) |
   | --- | --- | --- |
   | USB speed | Full-speed, 12M | **High-speed, 480M** |
   | `/proc/asound/card0/stream0` | `full speed`, packet size 104 | `high speed`, packet size 104, **`Data packet interval: 1000 us`** |
   | Throughput (arecord -D pulse, 48kHz) | 8.3% (24000/288000 байт за 3с) | **91.7%** (264000/288000) |
   | Throughput (16kHz) | 8.3% | **95.8%** |
   | Chunk cadence | 12000 байт раз в ~1.15-1.2с (пачками) | **12000 байт раз в ~128мс, стабильно** |
   | `oww_score` cadence | ~1.1Hz пачками | **~12.64 Hz** (avg delta 79.6мс, span 14с / 178 событий) |

   `oww_score` теперь обновляется на каденсе, практически идентичном целевому
   ~12.5Hz из "Merge conditions" (12.64Hz измерено живьём). `score` остаётся
   `0.001` во всех 178 событиях — это ОЖИДАЕМО: в комнате тишина, слово "адам"
   не произносилось, так что низкий score корректен. Условие "не застывает на
   ~0.001" из merge conditions относится к КАДЕНСУ обновления (раньше застывал
   на ~1Hz/redundant-пачках), а не к самому значению при отсутствии речи.

   **Корневая причина (эмпирически, на сегодня):** USB-кабель WebCamera был
   подключён к порту `1-2.2`, который негоциировал Full-Speed (12 Mbps) для
   этого устройства вместо High-Speed (480 Mbps) — устройство физически не
   могло передать данные быстрее ~8% номинала по этой шине, независимо от
   ОС/PipeWire/ALSA конфигурации (отсюда нерезультативность пп.1, 7, 8). Смена
   порта на `1-2.4` → High-Speed негоциация (подтверждено kernel-логом, дважды
   после resets) → throughput/каденс восстановились.

   **ОГОВОРКА (важно):** пользователь сообщил, что ранее (в предыдущих
   сессиях) уже пробовал переключать кабель на другие порты — без эффекта.
   Kernel-журнал не хранит историю дальше текущего boot (начинается с 18:05
   сегодня), так что сравнить с теми попытками нельзя — неизвестно, были ли
   те порты тоже Full-Speed, или дело не только в порте. Поэтому:
   - **Функциональный статус фазы** не зависит от точного механизма: ОБА merge
     condition подтверждены ЖИВЬЁМ на текущей конфигурации (порт `1-2.4` +
     WirePlumber Attempt 3) прямо сейчас — это факт, измеренный несколько раз.
   - **Объяснение "почему именно этот порт сработал, а другие раньше — нет"**
     остаётся неподтверждённым. Возможные факторы: не все downstream-порты
     USB-хаба Jetson Orin NX равноценны по поддержке High-Speed для этого
     устройства; либо комбинация порт+WirePlumber-конфиг (Attempt 3 появился
     только сегодня, 17:17) важна, а порт сам по себе раньше не помогал без
     него.
   - **Диагностика при регрессии**: `cat /proc/asound/card0/stream0` (или
     соответствующий card) — если видно `full speed`, throughput будет ~8% и
     `oww_score` снова "застынет" на низком каденсе; пробовать другой
     физический порт + проверять `high speed`/`Data packet interval: 1000 us`
     заново. Не считать "сменить порт" гарантированным fix-once-and-forever.

   **Attempt 3 (п.7, WirePlumber period-size override) остаётся в системе** —
   не мешает, но при High-Speed устройстве, возможно, уже не нужен
   (`node.max-latency` теперь может быть некритичен при штатном throughput).
   Не трогать без отдельной проверки — система сейчас РАБОТАЕТ.

   **Осталось для смыкания фазы:** полный цикл wake→listen→reply с реальным
   произнесением "адам" на живом железе (вторая часть merge condition).

10. **ЗАКРЫТО (2026-06-13) — voice loop подтверждён + находка перенесена на SmartFlora.**

    Пользователь подтвердил: Адам реагирует на обращения по слову "адам"
    (wake→listen→reply проходит на живом железе). Оба merge condition фазы
    выполнены.

    **Сверка с SmartFlora (Phase 41, `local_mic_reader.py`):** их диагностика
    дошла до того же `node.max-latency=48000/48000` и того же WirePlumber
    override (Attempt 1 в истории `51-webcamera-latency.lua`), но получила
    только 1.5→3.5Hz (партиал, цель 12.5Hz) — узкое место было НИЖЕ их слоя
    диагностики, тот же USB Full-Speed дефект из п.9. Физический фикс
    (смена порта) — вне git, действует системно для обеих веток.

    Прямая проверка: воспроизведён точный `_start_process()` из
    `local_mic_reader.py` (динамический `_find_pulse_source("webcamera")` →
    резолвит текущий `...capture.0.0` узел корректно; + `PULSE_LATENCY_MSEC=20`)
    на текущем (после смены порта) железе → **95.2% throughput, 128мс
    стабильный каденс** — идентично результату п.9. Их захардкоженный
    `PULSE_SOURCE=...mono-fallback` в `adam-orchestrator.service` неактуален,
    но не мешает — перетирается `_start_process()`.

    **Вывод:** Phase 41 на SmartFlora теперь фактически разблокирована тем же
    физическим фиксом, без изменений кода. Полноценный git-merge веток не
    требуется — расхождение чисто архитектурное (`local_mic_reader.py` vs
    `_run_local`), решение какая архитектура остаётся "канонической" — отдельный
    вопрос, не блокирующий закрытие фазы 36. Кросс-референс добавлен в
    `41-03-SUMMARY.md` на ветке SmartFlora.

    **Эта ветка (`audio-pipeline-restoration`) готова к мёржу в `main`** —
    единственное содержательное изменение: `PULSE_SOURCE=...capture.0.0` в
    `deploy/systemd/adam-orchestrator.service` (уже задеплоено и работает) +
    WirePlumber-конфиг `51-webcamera-latency.lua` (вне git, общесистемный,
    уже активен).

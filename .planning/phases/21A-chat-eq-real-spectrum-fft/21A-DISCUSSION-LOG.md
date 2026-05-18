# Phase 21A: Chat EQ Real Spectrum — реальный FFT в виджете эквалайзера - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 21A-chat-eq-real-spectrum-fft
**Areas discussed:** Формат события, Cadence + число bands, Полоса и шкала, Нормализация в [0..1]

---

## Pre-discussion alignment (до AskUserQuestion в этой сессии)

Зафиксировано на этапе анализа отчёта по эквалайзеру:

| Решение | Источник |
|--------|----------|
| Сохранить отображение OWW score (циан) и threshold (оранжевый пунктир) | Прямое требование пользователя |
| Заменить иллюзорный «спектр» на реальный FFT, без magic-чисел и синусоид | Прямое требование пользователя |
| Цвет бара — градиент по уровню (зелёный → жёлтый → красный), без отражения mic_source | Ответ на AskUserQuestion «Только pic-redness» |
| FFT источник — backend (Jetson MicReader), не Web Audio в браузере | Ответ на AskUserQuestion «Делаем по-настоящему: FFT на Jetson + новое событие» |
| Бары без peak-hold, без decay (максимально честное отражение текущего FFT-кадра) | Прямое требование пользователя |
| Magic-числа из текущего кода (4.0, 0.87, BAR_N, EQ_SHAPE) — устранить | Из отчёта + Config-First правило |
| Починить потенциальную SSE-утечку при unmount | Прямое требование пользователя |
| Phase numbering: Phase 21A как слайс Phase 21 (UI Rebuild) | Ответ на AskUserQuestion |
| Ветка: остаёмся на V-S09.1-Audio_out, создаём BRANCH.md | Ответ на AskUserQuestion |

---

## Cadence + число bands

### Cadence публикации FFT

| Option | Description | Selected |
|--------|-------------|----------|
| 10 Hz | Та же cadence что audio_level сейчас. Минус: без сглаживания прыгает резко. | |
| 25 Hz (каждый 2-й фрейм, 40 ms) | Сбалансированный вариант, в 2.5× SSE-трафика. | ✓ |
| 50 Hz (каждый фрейм, 20 ms) | Максимум. 5× SSE-трафика, спамит events.jsonl. | |
| Опция в Config.json (по умолчанию 25 Hz) | spectrum_cadence_hz, hot-reload. | |

**User's choice:** 25 Hz
**Notes:** Параметр всё равно идёт в Config.json (по Config-First), default 25 Hz зафиксирован.

### Число bands

| Option | Description | Selected |
|--------|-------------|----------|
| 24 (серединка) | Похоже на текущие 28 по плотности. | ✓ |
| 16 (крупные бары) | Меньше jitter без сглаживания, видны форманты. Менее «эквалайзерно». | |
| 32 (детально) | Больше прыгает без сглаживания, «FFT-вид». | |
| Опция в Config.json (по умолчанию 24) | spectrum_bands, hot-reload. | |

**User's choice:** 24
**Notes:** Параметр в Config.json по Config-First.

---

## Полоса и шкала

| Option | Description | Selected |
|--------|-------------|----------|
| 80 Hz – 4 kHz, log-частотная (voice-focused) | Информативный вид для речи; бары равномерно заполняются. | |
| 80 Hz – 8 kHz, log (весь спектр до Nyquist) | Физически полный спектр. При речи правые 8-10 баров почти всегда пустые — но честно. | ✓ |
| 80 Hz – 4 kHz, mel-шкала | Психоакустическая, требует numpy mel-фильтра. | |
| Linear 80 Hz – 4 kHz | Равные полосы по Hz. При речи 90% энергии в нижних барах. | |

**User's choice:** 80 Hz – 8 kHz, log
**Notes:** «Честный» подход — пустые правые бары при речи покажут реальную природу человеческого голоса. Согласуется с общим решением «максимально честно».

---

## Нормализация в [0..1]

| Option | Description | Selected |
|--------|-------------|----------|
| dBFS с опорным диапазоном (напр. −60 dB → 0 dB) | Стандарт. Стабильно без сглаживания. | ✓ |
| sqrt-сжатие как у RMS (min(1, (mag/N)**0.5)) | Согласованность с VU-meter. Минус: шум floor поднимается. | |
| Rolling-max auto-gain (окно ~3 с) | Адаптивно. Минус: «красный пик» теряет смысл. | |
| Linear по фиксированному max | Простейший. Тихая речь почти не видна. | |

**User's choice:** dBFS с опорным диапазоном (−60 dB → 0 dB)
**Notes:** Параметры floor/ceiling в Config.json (-60 dBFS / 0 dBFS по умолчанию).

---

## Формат события

| Option | Description | Selected |
|--------|-------------|----------|
| Отдельное audio_spectrum (своя cadence 25 Hz) | audio_level остаётся 10 Hz. Чистое разделение, нулевой риск для legacy. | |
| Расширить audio_level полем bands[] | Cadence audio_level вырастает до 25 Hz. events.jsonl × 2.5. | ✓ |

**User's choice:** Расширить audio_level полем bands[]
**Notes:** Подразумевается ускорение audio_level до 25 Hz целиком. Если нагрузка на events.jsonl окажется проблемой — рассмотреть writing-side sampler в plan-phase, сохранив SSE-cadence.

---

## Claude's Discretion

- Конкретная FFT-библиотека (`numpy.fft.rfft` vs `scipy.fft`). Default — numpy (уже в зависимостях через silero/whisperx стек).
- Структура precomputed log-binning таблицы (форма данных, регенерация при hot-reload параметров).
- Точная форма Config-ключей для цветовых границ: один объект `spectrum_color_thresholds: {yellow, red}` или плоские ключи.
- Алгоритм down-mix stereo → mono для FFT (простое (L+R)/2 vs sqrt((L²+R²)/2)).
- Размер FFT-окна: 160 samples = 20 ms = один frame_bytes. Зерополнение до степени 2 (например 256) для скорости и плотности bin — на планировщике.
- Конкретная стратегия mitigation для роста events.jsonl × 2.5 (downsample в writing-side, сжатие, ротация).

## Deferred Ideas

- Sampling логирования audio_level в jsonl: писать в файл каждое N-е событие если объём становится критичным.
- Mel-шкала или полосы по формантам речи: если log-шкала визуально не зайдёт, переключить.
- Спектрограмма-водопад (waterfall) вместо bars: альтернативное представление, отдельная фаза.
- Per-channel FFT (отдельный спектр L/R): стерео-источник есть, текущее решение — mono.

## Из Phase 21 (UI Rebuild) — НЕ в этой фазе

Дефертится в Phase 21 (UI Rebuild):

- Перегруппировка параметров UI по доменным блокам
- UI-настройка silence timeout (command_endpointing_ms, reply_window_sec)
- Управление громкостью TTS (output device volume) через UI

import { api } from "../api.js";
import { state } from "../state.js";
import { toast } from "../widgets/toast.js";
import { createWakeMeter, createCalibrateButton } from "../widgets/wakeMeter.js";

function el(tag, attrs, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v != null && v !== false) node.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null || c === false) return;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return node;
}

function getNested(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

function setNested(obj, path, value) {
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (cur[keys[i]] == null || typeof cur[keys[i]] !== "object") cur[keys[i]] = {};
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return obj;
}

// Unified schema. Each group has:
//   source: "config" | "tuning"
//   section: dotted path for config (e.g. "services.llm")
//   tuningSectionPath: tuning group key (e.g. "llm")
//   title: display title
//   fields: array of field descriptors
//
// Config field types: text | number | bool | select | textarea | audiodevice | voices | csv_array
// Tuning field types: bool | int | float | string | enum | text (alias for string)
const SCHEMA = [
  // ── Agent ────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "agent", title: "Агент",
    fields: [
      { key: "mode", label: "Режим работы", type: "select",
        choices: ["maintenance", "idle", "listening", "performance", "exhibition"],
        hint: "maintenance — техническое обслуживание · exhibition — выставочный" },
      { key: "language", label: "Язык", type: "select",
        choices: ["ru-RU", "en-US"],
        hint: "основной язык взаимодействия" },
      { key: "history_turns", label: "История диалога (ходов)", type: "number",
        hint: "2–4 рекомендуется · меньше = быстрее инференс" },
      { key: "name", label: "Имя агента", type: "text" },
    ],
  },

  // ── LLM config ───────────────────────────────────────────────────────────────
  {
    source: "config", section: "services.llm", title: "LLM · инфраструктура",
    fields: [
      { key: "base_url", label: "Адрес службы LLM", type: "text",
        hint: "http://127.0.0.1:8081/v1" },
      { key: "model", label: "Модель", type: "text" },
      { key: "num_ctx", label: "Размер контекста (токенов)", type: "number",
        hint: "8192 рекомендуется · меньше = быстрее, но обрезает историю" },
      { key: "timeout_sec", label: "Таймаут (с)", type: "number",
        hint: "рекомендуется 60" },
    ],
  },

  // ── LLM tuning ───────────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "llm", title: "LLM · runtime (персона)",
    fields: [
      { key: "temperature",          label: "Температура",           type: "float", min: 0, max: 2, step: 0.05,
        hint: "0.7 рекомендуется · выше = творчески, ниже = точнее" },
      { key: "max_tokens",           label: "Макс. токенов ответа",  type: "int",   min: 10, max: 2000,
        hint: "60–100 рекомендуется для выставки" },
      { key: "response_word_target", label: "Целевая длина (слов)",  type: "int",   min: 5, max: 200,
        hint: "15–30 рекомендуется" },
    ],
  },

  // ── Prompt builder (tuning) ───────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "prompt", title: "Сборка промта",
    fields: [
      { key: "history_turns",   label: "Ходов истории",            type: "int",  min: 0, max: 50,
        hint: "2–4 рекомендуется · меньше = быстрее · дублирует agent.history_turns в Config" },
      { key: "include_scene",   label: "Включить описание сцены",  type: "bool",
        hint: "добавляет VLM-описание в промт" },
      { key: "include_sensors", label: "Включить данные сенсоров", type: "bool" },
    ],
  },

  // ── Voice tuning ─────────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "voice", title: "Голос (runtime)",
    fields: [
      { key: "speaker",          label: "Диктор",        type: "string",
        hint: "aidar · baya · kseniya · xenia · eugene · random" },
      { key: "speed_multiplier", label: "Скорость речи", type: "float", min: 0.8, max: 1.6, step: 0.05,
        slider: true,
        hint: "1.0 = нормально · 1.25 = живее (рекомендуется) · 1.5 = быстро" },
      { key: "volume",           label: "Громкость",     type: "float", min: 0, max: 2, step: 0.05,
        hint: "1.0 = нормально" },
    ],
  },

  // ── TTS config ───────────────────────────────────────────────────────────────
  {
    source: "config", section: "services.tts", title: "TTS · Silero",
    fields: [
      { key: "base_url", label: "Адрес службы TTS", type: "text",
        hint: "http://127.0.0.1:8082" },
      { key: "output_device", label: "Аудиовыход (ALSA)", type: "audiodevice",
        hint: "plughw:1,3 = HDMI 0 · default = PulseAudio" },
      { key: "speaker", label: "Диктор (config)", type: "voices",
        hint: "конфигурационное значение; runtime-значение выше" },
      { key: "timeout_sec", label: "Таймаут (с)", type: "number" },
    ],
  },

  // ── OWW · Wake word ──────────────────────────────────────────────────────────
  {
    source: "config", section: "wake_word", title: "OWW · Wake word",
    fields: [
      { key: "threshold",     label: "Порог срабатывания (OWW score)", type: "number",
        hint: "0–1 · 0.25 рекомендуется · можно настроить ползунком ниже или калибровкой",
        min: 0, max: 1, step: 0.05 },
      { key: "debounce_hits", label: "Подтверждений подряд", type: "number",
        hint: "2 рекомендуется · больше = меньше ложных срабатываний",
        min: 1, max: 20, step: 1 },
      { key: "vad_threshold", label: "VAD порог (Silero внутри OWW)", type: "number",
        hint: "0–1 · 0 — выключено · выше = строже фильтрует тишину",
        min: 0, max: 1, step: 0.05 },
      { key: "wake_silence_timeout_sec", label: "Тишина после wake word (с)", type: "number",
        hint: "5 рекомендуется · после истечения — обратно в standby",
        min: 0.5, max: 10, step: 0.5 },
    ],
    extras: () => buildWakeWordExtras(),
  },

  // ── ASR · WhisperX ───────────────────────────────────────────────────────────
  {
    source: "config", section: "services.asr", title: "ASR · WhisperX",
    fields: [
      { key: "model", label: "Модель WhisperX", type: "select",
        choices: ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        hint: "tiny/base — быстро, точность низкая · small — баланс · medium — рекомендуется · large-v2/v3 — максимум точности, 10+ ГБ VRAM" },
      { key: "command_endpointing_ms", label: "Endpointing — пауза перед отправкой (мс)", type: "number",
        hint: "3000 рекомендуется · VAD ждёт такую паузу тишины, затем отправляет фразу в распознавание",
        min: 200, max: 5000, step: 100 },
      { key: "reply_window_sec", label: "Reply window — ожидание ответа (с)", type: "number",
        hint: "4.0 · после ответа Адама открывается окно, в котором зритель может говорить без wake word",
        min: 1, max: 30, step: 0.5 },
      { key: "reply_absolute_deadline_sec", label: "Reply window — жёсткий дедлайн (с)", type: "number",
        hint: "12.0 · принудительное закрытие reply window даже при наличии звука",
        min: 5, max: 60, step: 1 },
      { key: "reply_window_expired_action", label: "Reply window — действие по истечении", type: "select",
        choices: ["standby", "stop"],
        hint: "standby — остаётся в ожидании wake word · stop — отключает микрофон (принудительно, как в exhibition)" },
      { key: "webrtc_vad_aggressiveness", label: "WebRTC VAD — агрессивность", type: "number",
        sourceSection: "media.audio",
        hint: "0–3 · 2 = баланс, 3 = строго · выше = меньше ложных срабатываний на фоновый шум, но возможны пропуски тихой речи",
        min: 0, max: 3, step: 1 },
      { key: "timeout_sec", label: "Таймаут HTTP-запроса к ASR (с)", type: "number",
        hint: "30 рекомендуется" },
    ],
  },

  // ── VLM config ───────────────────────────────────────────────────────────────
  {
    source: "config", section: "services.vlm", title: "VLM · описание сцены",
    fields: [
      { key: "base_url",      label: "Адрес службы VLM", type: "text",
        hint: "http://127.0.0.1:8084" },
      { key: "model",         label: "Модель VLM",       type: "text" },
      { key: "max_new_tokens", label: "Макс. токенов",   type: "number",
        hint: "24–48 достаточно для описания сцены" },
      { key: "timeout_sec",   label: "Таймаут (с)",      type: "number",
        hint: "20 рекомендуется" },
      { key: "prompt",        label: "Промт VLM",        type: "textarea",
        hint: "инструкция для описания кадра" },
    ],
  },

  // ── Video ─────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "media.video", title: "Видеопоток",
    fields: [
      { key: "primary", label: "Источник видео", type: "select",
        choices: ["jetson_gstreamer", "esp_mjpeg"],
        hint: "jetson_gstreamer — CSI/USB через GStreamer · esp_mjpeg — MJPEG с ESP32 (резерв)" },
      { key: "gstreamer_pipeline", label: "GStreamer-конвейер", type: "textarea" },
      { key: "preview_enabled", label: "Предпросмотр включён", type: "bool" },
      { key: "camera_capture_interval_sec", label: "Интервал кадра (с)", type: "number",
        hint: "0.5 рекомендуется" },
    ],
  },

  // ── Camera ────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "media.video", title: "Камера",
    fields: [
      { key: "primary", label: "Источник камеры", type: "select",
        choices: ["esp_mjpeg", "jetson_gstreamer"],
        hint: "esp_mjpeg = ESP32 CAM · авто-переключение на Jetson при недоступности" },
    ],
  },

  // ── Audio ─────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "media.audio", title: "Микрофон и VAD",
    fields: [
      { key: "mic_source", label: "Источник микрофона", type: "select",
        choices: ["esp32", "local"],
        hint: "esp32 = INMP441 dual mic · авто-переключение на pulse при недоступности" },
      { key: "input_device", label: "Микрофон (ALSA, резерв)", type: "audioinput",
        hint: "pulse = PulseAudio · hw:X,Y = аппаратное устройство · используется при недоступности ESP32" },
      { key: "sample_rate", label: "Частота дискретизации (Гц)", type: "select",
        choices: ["8000", "16000", "22050", "44100"],
        hint: "рекомендуется 16000",
        toValue: Number, fromValue: String },
      { key: "min_speech_ms", label: "Мин. длина реплики (мс)", type: "number",
        hint: "250–404 рекомендуется" },
      { key: "max_segment_ms", label: "Макс. длина сегмента (мс)", type: "number",
        hint: "9000 рекомендуется" },
    ],
  },

  // ── Scene worker ──────────────────────────────────────────────────────────────
  {
    source: "config", section: "media", title: "Воркер описания сцены",
    fields: [
      { key: "scene_worker_enabled",  label: "Описание сцены активно", type: "bool" },
      { key: "scene_interval_sec",    label: "Интервал описания (с)",  type: "number",
        hint: "3–8 рекомендуется · реже = меньше нагрузка GPU" },
      { key: "scene_stale_after_sec", label: "Устаревание (с)",        type: "number",
        hint: "обычно 2–3× от интервала" },
      { key: "scene_context_count",   label: "Кол-во сцен в контексте", type: "number",
        hint: "1 рекомендуется" },
    ],
  },

  // ── Episodic memory ───────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "memory.episodic", title: "Память · эпизоды",
    fields: [
      { key: "enabled",                    label: "Запись эпизодов",             type: "bool" },
      { key: "salience_threshold",         label: "Порог значимости",            type: "float", min: 0, max: 1, step: 0.05,
        hint: "0–1 · минимальный балл для записи эпизода" },
      { key: "decay_days",                 label: "Дней до забывания",           type: "int",   min: 1, max: 365 },
      { key: "duration_normalize_seconds", label: "Норматив длительности (с)",   type: "int",   min: 30, max: 3600 },
      { key: "highlights_max_per_episode", label: "Макс. маркеров на эпизод",    type: "int",   min: 1, max: 50 },
    ],
  },

  {
    source: "tuning", tuningSectionPath: "memory.episodic.weights", title: "Веса значимости эпизода",
    fields: [
      { key: "introduced_name", label: "Имя зрителя",       type: "float", min: 0, max: 1, step: 0.05,
        hint: "сумма всех весов должна быть 1.0" },
      { key: "duration",        label: "Длительность",       type: "float", min: 0, max: 1, step: 0.05 },
      { key: "themes",          label: "Темы",               type: "float", min: 0, max: 1, step: 0.05 },
      { key: "tone",            label: "Тональность",        type: "float", min: 0, max: 1, step: 0.05 },
      { key: "echoes_used",     label: "Использованные эхо", type: "float", min: 0, max: 1, step: 0.05 },
      { key: "new_question",    label: "Новый вопрос",       type: "float", min: 0, max: 1, step: 0.05 },
    ],
  },

  // ── Echoes ────────────────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "echoes", title: "Эхо (обрывки воспоминаний)",
    fields: [
      { key: "enabled",               label: "Активны",                      type: "bool" },
      { key: "global_cooldown_turns", label: "Перерыв между эхо (ходов)",    type: "int",   min: 0 },
      { key: "per_echo_cooldown_days", label: "Перерыв одного эхо (дней)",   type: "int",   min: 0 },
      { key: "match_threshold",       label: "Порог совпадения",             type: "float", min: 0, max: 1, step: 0.05 },
      { key: "weight_multiplier",     label: "Множитель весов",              type: "float", min: 0, max: 5, step: 0.1 },
      { key: "matcher_type",          label: "Метод сравнения",              type: "enum",  options: ["tag", "embedding"] },
    ],
  },

  // ── Chinese ───────────────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "chinese", title: "Китайские вкрапления",
    fields: [
      { key: "enabled",               label: "Активны",          type: "bool" },
      { key: "global_cooldown_turns", label: "Перерыв (ходов)",  type: "int",   min: 0 },
      { key: "per_echo_cooldown_days", label: "Перерыв одного (дней)", type: "int", min: 0 },
      { key: "match_threshold",       label: "Порог совпадения", type: "float", min: 0, max: 1, step: 0.05 },
      { key: "weight_multiplier",     label: "Множитель весов",  type: "float", min: 0, max: 5, step: 0.1 },
      { key: "audio_mode",            label: "Режим аудио",      type: "enum",
        options: ["prerendered_only", "prerendered_with_text_fallback", "text_only"] },
    ],
  },

  // ── Session ───────────────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "session", title: "Сессия",
    fields: [
      { key: "end_strategy",        label: "Стратегия завершения",       type: "enum",
        options: ["vad_silence", "face_lost", "combined", "idle_with_grace", "event_signal"] },
      { key: "vad_silence_seconds", label: "Тишина для завершения (с)",  type: "int",  min: 5,
        hint: "15–30 рекомендуется" },
      { key: "face_lost_seconds",   label: "Лицо потеряно — задержка (с)", type: "int", min: 2 },
      { key: "grace_message",       label: "Прощальная фраза",           type: "string" },
    ],
  },

  // ── Scene director ────────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "scene_director", title: "Сцены моторики (SceneDirector)",
    fields: [
      { key: "enabled",                          label: "Активен",                   type: "bool" },
      { key: "sustain_seconds",                  label: "Время удержания сцены (с)", type: "int", min: 1 },
      { key: "cooldown_between_changes_seconds", label: "Пауза между сменами (с)",  type: "int", min: 0 },
      { key: "hysteresis_seconds",               label: "Гистерезис (с)",           type: "int", min: 0 },
    ],
  },

  // ── Power ─────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "power", title: "Питание (nvpmodel)",
    fields: [
      { key: "required_mode_id", label: "Режим питания (nvpmodel ID)", type: "select",
        choices: ["0", "1", "2"],
        hint: "0 = MAXN (обязателен для выставки)",
        toValue: Number, fromValue: String },
      { key: "require_jetson_clocks", label: "Требовать jetson_clocks", type: "bool",
        hint: "фиксирует частоты CPU/GPU на максимум" },
      { key: "enforce_in_exhibition", label: "Блокировать без MAXN (exhibition)", type: "bool" },
    ],
  },

  // ── MCU ───────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "mcu", title: "Модуль ESP32",
    fields: [
      { key: "base_url",    label: "Адрес ESP32",         type: "text",
        hint: "http://192.168.0.171" },
      { key: "speaker_url", label: "Адрес динамика ESP32", type: "text" },
      { key: "timeout_sec", label: "Таймаут (с)",          type: "number",
        hint: "1 рекомендуется — иначе блокирует диалог" },
      { key: "idle_scene",  label: "Сцена простоя",        type: "text" },
    ],
  },

  // ── Safety ────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "safety", title: "Безопасность и моторика",
    fields: [
      { key: "half_duplex_mute",         label: "Mute микрофона во время TTS", type: "bool",
        hint: "предотвращает самоответ агента" },
      { key: "motor_default_duration_ms", label: "Длительность мотора (мс)",  type: "number",
        hint: "900 рекомендуется" },
      { key: "motor_max_duration_ms",     label: "Макс. длительность (мс)",   type: "number",
        hint: "не более 2500" },
      { key: "motor_cooldown_ms",         label: "Охлаждение мотора (мс)",    type: "number" },
    ],
  },

  // ── Sounds ────────────────────────────────────────────────────────────────────
  {
    source: "config", section: "sounds", title: "Системные звуки",
    fields: [
      { key: "enabled",             label: "Включены",                    type: "bool" },
      { key: "success_path",        label: "Звук успеха (путь к файлу)", type: "text" },
      { key: "local_output_device", label: "Устройство вывода звуков",   type: "text" },
    ],
  },

  // ── Diagnostics ───────────────────────────────────────────────────────────────
  {
    source: "tuning", tuningSectionPath: "diagnostics", title: "Диагностика",
    fields: [
      { key: "log_level",       label: "Уровень логирования",    type: "enum",
        options: ["debug", "info", "warning", "error"] },
      { key: "metrics_enabled", label: "Сбор метрик",            type: "bool",
        hint: "пишет inference_metrics.jsonl" },
      { key: "trace_prompts",   label: "Сохранять полный промт", type: "bool",
        hint: "для панели Промты · потребляет память" },
    ],
  },
];

// ── Field helpers ─────────────────────────────────────────────────────────────

function buildDeviceSelect(devices, currentValue, onChange) {
  const sel = el("select", { class: "select" });
  if (currentValue && !devices.find((d) => d.name === currentValue)) {
    const opt = el("option", { value: currentValue, selected: "selected" });
    opt.textContent = `${currentValue} (текущее)`;
    sel.appendChild(opt);
  }
  if (!devices.length) {
    const opt = el("option", { value: currentValue ?? "" });
    opt.textContent = currentValue ?? "—";
    sel.appendChild(opt);
  }
  devices.forEach((d) => {
    const opt = el("option", { value: d.name, selected: d.name === currentValue ? "selected" : null });
    const desc = d.description ? ` · ${d.description.slice(0, 42)}` : "";
    opt.textContent = `${d.name}${desc}`;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", () => onChange(sel.value));
  return sel;
}

function buildVoiceSelect(voices, currentValue, onChange) {
  const sel = el("select", { class: "select" });
  voices.forEach((v) => {
    const name = typeof v === "string" ? v : v.name;
    const opt = el("option", { value: name, selected: name === currentValue ? "selected" : null });
    opt.textContent = name;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", () => onChange(sel.value));
  return sel;
}

function fieldInput(field, value, onChange, ctx) {
  const { audioDevices = [], inputDevices = [], ttsVoices = [] } = ctx || {};
  const type = field.type;

  if (type === "csv_array") {
    const displayVal = Array.isArray(value) ? value.join(", ") : (value ?? "");
    const input = el("input", { class: "input", type: "text" });
    input.value = displayVal;
    input.addEventListener("change", () => {
      onChange(input.value.split(",").map((s) => s.trim()).filter(Boolean));
    });
    return input;
  }

  if (type === "audiodevice") return buildDeviceSelect(audioDevices, value ?? "", onChange);
  if (type === "audioinput")  return buildDeviceSelect(inputDevices, value ?? "", onChange);
  if (type === "voices")      return buildVoiceSelect(ttsVoices, value ?? "", onChange);

  if (type === "bool") {
    const select = el("select", { class: "select" }, [
      el("option", { value: "true",  selected: value === true  ? "selected" : null }, "включено"),
      el("option", { value: "false", selected: value === false ? "selected" : null }, "выключено"),
    ]);
    select.addEventListener("change", () => onChange(select.value === "true"));
    return select;
  }

  if (type === "select") {
    const fromValue = field.fromValue || ((v) => v);
    const toValue   = field.toValue   || ((v) => v);
    const displayVal = fromValue(value ?? "");
    const select = el("select", { class: "select" });
    (field.choices || []).forEach((c) => {
      const opt = el("option", { value: c, selected: c === displayVal ? "selected" : null });
      opt.textContent = c;
      select.appendChild(opt);
    });
    select.addEventListener("change", () => onChange(toValue(select.value)));
    return select;
  }

  if (type === "enum") {
    const select = el("select", { class: "select mono" });
    (field.options || []).forEach((opt) => {
      const o = el("option", { value: opt, selected: opt === value ? "selected" : null });
      o.textContent = opt;
      select.appendChild(o);
    });
    select.addEventListener("change", () => onChange(select.value));
    return select;
  }

  if (type === "textarea") {
    const ta = el("textarea", { class: "textarea", rows: 3 });
    ta.value = value ?? "";
    ta.addEventListener("change", () => onChange(ta.value));
    return ta;
  }

  // number | int | float | text | string
  const isNum = type === "number" || type === "int" || type === "float";

  // ── Slider variant (opt-in via `slider: true` on numeric field) ────────────
  if (isNum && field.slider) {
    const slider = el("input", {
      class: "input slider",
      type: "range",
      min: field.min ?? 0,
      max: field.max ?? 1,
      step: field.step ?? (type === "int" ? "1" : "0.01"),
      style: "flex:1; min-width:120px; cursor:pointer",
    });
    const init = value ?? field.min ?? 0;
    slider.value = init;
    const valueLabel = el("span", {
      class: "mono",
      style: "min-width:48px; text-align:right; color:var(--accent); font-size:12px; font-weight:600",
    }, Number(init).toFixed(2));
    slider.addEventListener("input", () => {
      valueLabel.textContent = Number(slider.value).toFixed(2);
    });
    slider.addEventListener("change", () => {
      const v = type === "int" ? parseInt(slider.value, 10) : parseFloat(slider.value);
      if (Number.isNaN(v)) { toast(`${field.label}: ожидалось число`, "bad"); return; }
      onChange(v);
    });
    return el("div", { style: "display:flex; align-items:center; gap:10px; padding:4px 0" }, [
      slider, valueLabel,
    ]);
  }

  const attrs = { class: "input", type: isNum ? "number" : "text" };
  if (isNum) {
    if (field.min != null)  attrs.min  = field.min;
    if (field.max != null)  attrs.max  = field.max;
    if (field.step != null) attrs.step = field.step;
    else if (type === "int") attrs.step = "1";
    else attrs.step = "any";
  }
  const input = el("input", attrs);
  input.value = value ?? "";
  input.addEventListener("change", () => {
    if (isNum) {
      const v = type === "int" ? parseInt(input.value, 10) : parseFloat(input.value);
      if (Number.isNaN(v)) { toast(`${field.label}: ожидалось число`, "bad"); return; }
      onChange(v);
    } else {
      onChange(input.value);
    }
  });
  return input;
}

// ── Save helpers ──────────────────────────────────────────────────────────────

async function saveConfigField(section, key, value, status) {
  status.classList.remove("ok", "warn", "bad");
  status.classList.add("warn");
  status.textContent = "сохранение…";
  try {
    const res = await api.patch("/api/config", { section, patch: { [key]: value } });
    status.classList.remove("warn");
    status.classList.add("ok");
    status.textContent = `ok · ${(res.restarted || []).join(", ") || "сохранено"}`;
    setTimeout(() => { status.textContent = ""; status.classList.remove("ok"); }, 2500);
  } catch (e) {
    status.classList.remove("warn");
    status.classList.add("bad");
    status.textContent = "ошибка";
    toast(`${section}.${key}: ${e.message}`, "bad", 5000);
  }
}

async function saveTuningField(tuningSectionPath, key, value, status) {
  status.classList.remove("ok", "warn", "bad");
  status.classList.add("warn");
  status.textContent = "сохранение…";
  try {
    const patch = {};
    setNested(patch, `${tuningSectionPath}.${key}`, value);
    await api.raw("/api/tuning", { method: "PUT", body: patch });
    status.classList.remove("warn");
    status.classList.add("ok");
    status.textContent = "сохранено ✓";
    setTimeout(() => { status.textContent = ""; status.classList.remove("ok"); }, 2500);
  } catch (e) {
    status.classList.remove("warn");
    status.classList.add("bad");
    status.textContent = "ошибка";
    toast(`${tuningSectionPath}.${key}: ${e.message}`, "bad", 5000);
  }
}

// ── OWW extras ────────────────────────────────────────────────────────────────
// Adds a draggable wake-word meter + calibration button to the OWW card.
// The meter widget subscribes to SSE on its own; both the meter and the
// number-field above it stay in sync via the `wake_sensitivity_updated`
// event that the orchestrator emits on every PATCH.
function buildWakeWordExtras() {
  const meter = createWakeMeter({ draggable: true, height: 96 });
  const { btn: calibrateBtn, status: calibStatus } = createCalibrateButton();
  return el("div", { style: "display:flex; flex-direction:column; gap:6px; margin-top:10px" }, [
    el("div", { style: "display:flex; align-items:center; gap:8px" }, [
      el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Уровень микрофона · порог OWW"),
      el("span", { class: "spacer" }),
      calibrateBtn,
    ]),
    meter.canvas,
    el("div", { style: "display:flex; align-items:center; gap:8px" }, [
      el("span", { class: "dim", style: "font-size:10px; color:var(--muted); line-height:1.3" },
        "Перетащи оранжевую линию — порог wake-word. Циан — текущий OWW-score. Изменение сохраняется автоматически."),
      el("span", { class: "spacer" }),
      calibStatus,
    ]),
  ]);
}

// ── Render helpers ────────────────────────────────────────────────────────────

function renderFieldRow(field, value, buildInput) {
  const status = el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });
  const input = buildInput(field, status);
  return el("label", { style: "display:flex; flex-direction:column; gap:0" }, [
    el("div", { style: "display:flex; flex-direction:column; gap:2px; margin-bottom:4px" }, [
      el("div", { style: "display:flex; align-items:center; gap:6px; flex-wrap:wrap" }, [
        el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, field.label),
        status,
      ]),
      field.hint ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, field.hint) : null,
    ]),
    input,
  ]);
}

// ── Main mount ────────────────────────────────────────────────────────────────

export function mount(target) {
  let audioDevices = [];
  let inputDevices = [];
  let ttsVoices    = [];

  const container  = el("div", { class: "col" });
  const refreshBtn = el("button", { class: "btn", onclick: () => renderAll() }, "Перезагрузить");
  const audioDevicesBtn = el("button", {
    class: "btn btn-ghost",
    onclick: () => {
      const win = window.open("", "_blank", "width=560,height=680");
      if (win) {
        const rows = audioDevices.map((d) => `<b>${d.name}</b>\n  ${d.description || ""}`).join("\n\n");
        win.document.write(`<pre style="font-family:monospace;padding:16px;background:#0a0a0b;color:#43d17a;white-space:pre-wrap">${rows || "нет устройств"}</pre>`);
      } else {
        toast("Попап заблокирован — список в консоли", "warn");
        console.log(audioDevices);
      }
    },
  }, "Список аудиоустройств");

  const deviceStatusBar = el("div", {
    style: "display:flex; gap:16px; flex-wrap:wrap; padding:2px 0; font-size:11px; font-family:var(--font-mono); min-height:16px",
  });

  function paintDeviceStatus() {
    const s = state.get("status");
    deviceStatusBar.innerHTML = "";
    const camPrimary = s?.media?.video?.primary;
    if (camPrimary === "esp_mjpeg") {
      const isFallback = s?.camera?.active_source === "jetson_fallback";
      deviceStatusBar.appendChild(el("span", {
        style: `color:${isFallback ? "var(--warn)" : "var(--accent)"}`,
      }, isFallback ? "ESP32 CAM ↓ fallback: Jetson" : "ESP32 CAM ✓"));
    }
    const micCfg = s?.voice_loop?.mic_source;
    if (micCfg === "esp32") {
      const isFallback = s?.voice_loop?.esp_mic_fallback;
      deviceStatusBar.appendChild(el("span", {
        style: `color:${isFallback ? "var(--warn)" : "var(--accent)"}`,
      }, isFallback ? "INMP441 ↓ fallback: pulse" : "INMP441 ✓"));
    }
  }
  state.subscribe("status", paintDeviceStatus);
  paintDeviceStatus();

  target.appendChild(el("section", { class: "col" }, [
    el("div", { class: "row", style: "flex-wrap:wrap; gap:8px" }, [
      el("div", { class: "caps" }, "Настройки · изменения сохраняются сразу"),
      deviceStatusBar,
      el("span", { class: "spacer" }),
      audioDevicesBtn,
      refreshBtn,
    ]),
    container,
  ]));

  async function renderAll() {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "muted" }, [el("span", { class: "spinner" }), " загрузка…"]));

    const [devicesRes, inputDevicesRes, speakersRes, configRes, tuningRes] = await Promise.allSettled([
      api.get("/api/audio/devices"),
      api.get("/api/audio/input_devices"),
      api.get("/api/models/tts"),
      api.get("/api/config"),
      api.get("/api/tuning"),
    ]);

    if (devicesRes.status      === "fulfilled") audioDevices = devicesRes.value?.devices || [];
    if (inputDevicesRes.status === "fulfilled") inputDevices = inputDevicesRes.value?.devices || [];
    if (speakersRes.status === "fulfilled") {
      ttsVoices = (speakersRes.value?.available || []).map((v) => (typeof v === "string" ? v : v.name));
    }
    if (configRes.status === "rejected") {
      container.innerHTML = "";
      container.appendChild(el("div", { class: "card" }, el("div", { class: "card-body bad" },
        `Ошибка загрузки Config: ${configRes.reason?.message}`)));
      return;
    }

    const config  = configRes.value;
    const tuning  = tuningRes.status === "fulfilled" ? tuningRes.value : {};
    const ctx     = { audioDevices, inputDevices, ttsVoices };
    container.innerHTML = "";

    const cardGrid = el("div", { class: "card-grid" });

    SCHEMA.forEach((group) => {
      let sectionData;
      if (group.source === "config") {
        sectionData = getNested(config, group.section) || {};
      } else {
        sectionData = getNested(tuning, group.tuningSectionPath) || {};
      }

      const grid = el("div", { class: "field-grid" });

      group.fields.forEach((field) => {
        // sourceSection on a field overrides the group section for both load and save.
        const effectiveSection = (group.source === "config" && field.sourceSection)
          ? field.sourceSection
          : group.section;
        const fieldSectionData = (group.source === "config" && field.sourceSection)
          ? (getNested(config, field.sourceSection) || {})
          : sectionData;
        const value = fieldSectionData[field.key];
        const isWide = field.type === "textarea" || field.type === "csv_array" ||
          (field.type === "string" && String(value ?? "").length > 30) ||
          (field.type === "text"   && String(value ?? "").length > 40);

        const row = renderFieldRow(field, value, (f, st) => {
          if (group.source === "config") {
            return fieldInput(f, value, (v) => saveConfigField(effectiveSection, field.key, v, st), ctx);
          } else {
            return fieldInput(f, value, (v) => saveTuningField(group.tuningSectionPath, field.key, v, st), ctx);
          }
        });
        if (isWide) row.classList.add("field-wide");
        grid.appendChild(row);
      });

      const badge = group.source === "config"
        ? el("span", { class: "caps mono dim" }, group.section)
        : el("span", { class: "caps mono", style: "color:var(--accent-dim, var(--accent)); opacity:0.55" }, `tuning:${group.tuningSectionPath}`);

      const bodyChildren = [grid];
      if (typeof group.extras === "function") {
        const extra = group.extras(ctx, sectionData);
        if (extra) bodyChildren.push(extra);
      }

      const card = el("section", { class: "card" }, [
        el("div", { class: "card-header" }, [
          el("span", { class: "card-title" }, group.title),
          badge,
        ]),
        el("div", { class: "card-body" }, bodyChildren),
      ]);
      const hasTextarea = group.fields.some((f) => f.type === "textarea");
      if (hasTextarea) card.classList.add("card-full");
      cardGrid.appendChild(card);
    });

    container.appendChild(cardGrid);
    container.appendChild(el("div", { class: "muted", style: "font-size:12px; padding:8px 0" }, [
      el("span", null, "Модели и personas → "),
      el("a", { href: "#/models", style: "color:var(--accent)" }, "Модели"),
      el("span", null, " · Системный промт → "),
      el("a", { href: "#/persona", style: "color:var(--accent)" }, "Личность агента"),
      el("span", null, " · Параметры памяти → "),
      el("a", { href: "#/tuning", style: "color:var(--accent)" }, "Тюнинг (raw)"),
    ]));
  }

  renderAll();
  return () => {};
}

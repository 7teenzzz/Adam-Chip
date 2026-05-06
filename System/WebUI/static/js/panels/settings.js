import { api } from "../api.js";
import { toast } from "../widgets/toast.js";

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

// Curated form schema. Section path → list of fields.
// Field: { key, label, type, choices?, hint?, toValue?, fromValue? }
// Types: text | number | bool | select | textarea | audiodevice | voices | csv_array
const SCHEMA = [
  {
    section: "agent", title: "Агент",
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
  {
    section: "media.audio", title: "Микрофон и обнаружение речи",
    fields: [
      { key: "input_device", label: "Микрофон (ALSA-устройство)", type: "audiodevice",
        hint: "hw:1,0 = I2S ADMAIF1 (встроенный) · hw:2,0 = USB-микрофон" },
      { key: "sample_rate", label: "Частота дискретизации (Гц)", type: "select",
        choices: ["8000", "16000", "22050", "44100"],
        hint: "рекомендуется 16000",
        toValue: Number, fromValue: String },
      { key: "vad_threshold", label: "Порог VAD (СКО)", type: "number",
        hint: "600–800 для выставочного зала · 400–600 для тихого помещения" },
      { key: "min_speech_ms", label: "Мин. длина реплики (мс)", type: "number",
        hint: "рекомендуется 250–350" },
      { key: "max_segment_ms", label: "Макс. длина сегмента (мс)", type: "number",
        hint: "рекомендуется 8000–12000" },
    ],
  },
  {
    section: "services.tts", title: "Озвучка (TTS · Silero)",
    fields: [
      { key: "output_device", label: "Аудиовыход (ALSA-устройство)", type: "audiodevice",
        hint: "plughw:0,3 = HDMI 0 · plughw:2,0 = USB · default = PulseAudio" },
      { key: "base_url", label: "Адрес службы TTS", type: "text" },
      { key: "timeout_sec", label: "Таймаут (с)", type: "number" },
    ],
  },
  {
    section: "services.llm", title: "Языковая модель (LLM)",
    fields: [
      { key: "timeout_sec", label: "Таймаут (с)", type: "number",
        hint: "рекомендуется 60" },
    ],
  },
  {
    section: "services.asr", title: "Распознавание речи (ASR · Whisper)",
    fields: [
      { key: "sample_rate", label: "Частота дискретизации ASR (Гц)", type: "select",
        choices: ["8000", "16000", "22050", "44100"],
        hint: "рекомендуется 16000",
        toValue: Number, fromValue: String },
      { key: "base_url", label: "Адрес службы ASR", type: "text" },
      { key: "timeout_sec", label: "Таймаут (с)", type: "number" },
    ],
  },
  {
    section: "media", title: "Сцена и описание окружения (VLM)",
    fields: [
      { key: "scene_worker_enabled", label: "Описание сцены активно", type: "bool" },
      { key: "scene_interval_sec", label: "Интервал описания (с)", type: "number",
        hint: "5–15 рекомендуется" },
      { key: "scene_stale_after_sec", label: "Устаревание сцены через (с)", type: "number",
        hint: "обычно 2–3× от интервала" },
    ],
  },
  {
    section: "media.video", title: "Видеопоток",
    fields: [
      { key: "primary", label: "Источник видео", type: "select",
        choices: ["jetson_gstreamer", "esp_mjpeg"],
        hint: "jetson_gstreamer — CSI/USB через GStreamer · esp_mjpeg — MJPEG с ESP32 (резерв)" },
      { key: "gstreamer_pipeline", label: "GStreamer-конвейер", type: "textarea" },
      { key: "preview_enabled", label: "Предпросмотр включён", type: "bool" },
    ],
  },
  {
    section: "power", title: "Питание и производительность",
    fields: [
      { key: "required_mode_id", label: "Режим питания (nvpmodel ID)", type: "select",
        choices: ["0", "1", "2"],
        hint: "0 = MAXN (максимальная мощность, обязателен для выставки)",
        toValue: Number, fromValue: String },
      { key: "require_jetson_clocks", label: "Требовать jetson_clocks", type: "bool",
        hint: "фиксирует частоты CPU/GPU на максимум" },
      { key: "enforce_in_exhibition", label: "Блокировать без MAXN (exhibition)", type: "bool" },
    ],
  },
  {
    section: "mcu", title: "Модуль ESP32",
    fields: [
      { key: "base_url", label: "Адрес ESP32", type: "text",
        hint: "http://192.168.0.172" },
      { key: "speaker_url", label: "Адрес динамика ESP32", type: "text" },
      { key: "timeout_sec", label: "Таймаут (с)", type: "number",
        hint: "1 рекомендуется — иначе блокирует диалог" },
      { key: "idle_scene", label: "Сцена простоя", type: "text" },
    ],
  },
  {
    section: "safety", title: "Безопасность и моторика",
    fields: [
      { key: "half_duplex_mute", label: "Mute микрофона во время озвучки", type: "bool",
        hint: "предотвращает самоответ агента" },
      { key: "motor_default_duration_ms", label: "Длительность мотора по умолч. (мс)", type: "number",
        hint: "рекомендуется 900" },
      { key: "motor_max_duration_ms", label: "Макс. длительность мотора (мс)", type: "number",
        hint: "не более 2500" },
      { key: "motor_cooldown_ms", label: "Охлаждение мотора (мс)", type: "number" },
    ],
  },
  {
    section: "sounds", title: "Системные звуки",
    fields: [
      { key: "enabled", label: "Включены", type: "bool" },
      { key: "success_path", label: "Звук успеха (путь к файлу)", type: "text" },
      { key: "local_output_device", label: "Устройство вывода звуков", type: "text" },
    ],
  },
];

function isCompact(field) {
  return field.type === "number" || field.type === "bool" || field.type === "voices" ||
    (field.type === "select" && (field.choices || []).length <= 6) ||
    (field.type === "audiodevice");
}

function getNested(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

function buildDeviceSelect(devices, currentValue, onChange) {
  const sel = el("select", { class: "select" });
  // Always add the current value first if not in the fetched list
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
  const { audioDevices = [], ttsVoices = [] } = ctx || {};

  // csv_array: display as comma-separated, save as array
  if (field.type === "csv_array") {
    const displayVal = Array.isArray(value) ? value.join(", ") : (value ?? "");
    const input = el("input", { class: "input", type: "text" });
    input.value = displayVal;
    input.addEventListener("change", () => {
      const arr = input.value.split(",").map((s) => s.trim()).filter(Boolean);
      onChange(arr);
    });
    return input;
  }

  if (field.type === "audiodevice") {
    return buildDeviceSelect(audioDevices, value ?? "", onChange);
  }

  if (field.type === "voices") {
    return buildVoiceSelect(ttsVoices, value ?? "", onChange);
  }

  if (field.type === "bool") {
    const select = el("select", { class: "select" }, [
      el("option", { value: "true",  selected: value === true  ? "selected" : null }, "включено"),
      el("option", { value: "false", selected: value === false ? "selected" : null }, "выключено"),
    ]);
    select.addEventListener("change", () => onChange(select.value === "true"));
    return select;
  }

  if (field.type === "select") {
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

  if (field.type === "textarea") {
    const ta = el("textarea", { class: "textarea", rows: 3 });
    ta.value = value ?? "";
    ta.addEventListener("change", () => onChange(ta.value));
    return ta;
  }

  // text / number
  const isNum = field.type === "number";
  const input = el("input", { class: "input", type: isNum ? "number" : "text", step: isNum ? "any" : null });
  input.value = value ?? "";
  input.addEventListener("change", () => {
    if (isNum) {
      const v = Number(input.value);
      if (Number.isNaN(v)) { toast(`${field.label}: ожидалось число`, "bad"); return; }
      onChange(v);
    } else {
      onChange(input.value);
    }
  });
  return input;
}

async function saveField(section, key, value, status) {
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

function renderFieldRow(field, value, onSave) {
  const status = el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });
  const input = onSave(field, status);
  const labelRow = el("div", { style: "display:flex; flex-direction:column; gap:2px; margin-bottom:4px" }, [
    el("div", { style: "display:flex; align-items:center; gap:6px; flex-wrap:wrap" }, [
      el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, field.label),
      status,
    ]),
    field.hint ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, field.hint) : null,
  ]);
  return el("label", { style: "display:flex; flex-direction:column; gap:0" }, [labelRow, input]);
}

// ---------- Main mount ----------

export function mount(target) {
  let audioDevices = [];
  let ttsVoices    = [];

  const container = el("div", { class: "col" });
  const refreshBtn = el("button", { class: "btn", onclick: () => renderConfig() }, "Перезагрузить");
  const audioDevicesBtn = el("button", {
    class: "btn btn-ghost",
    onclick: () => {
      const win = window.open("", "_blank", "width=560,height=680");
      if (win) {
        const rows = audioDevices.map((d) => `<b>${d.name}</b>\n  ${d.description || ""}`).join("\n\n");
        win.document.write(`<pre style="font-family:monospace;padding:16px;background:#0a0a0b;color:#43d17a;white-space:pre-wrap">${rows || "нет устройств"}</pre>`);
      } else {
        console.log(audioDevices);
        toast("Попап заблокирован — список в консоли", "warn");
      }
    },
  }, "Список аудиоустройств");

  target.appendChild(el("section", { class: "col" }, [
    el("div", { class: "row" }, [
      el("div", { class: "caps" }, "Настройки · изменения сохраняются сразу"),
      el("span", { class: "spacer" }),
      audioDevicesBtn,
      refreshBtn,
    ]),
    container,
  ]));

  async function renderConfig() {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "muted" }, [el("span", { class: "spinner" }), " загрузка…"]));

    // Reload dynamic data on each render
    const [devicesRes, speakersRes, configRes] = await Promise.allSettled([
      api.get("/api/audio/devices"),
      api.get("/api/models/tts"),
      api.get("/api/config"),
    ]);
    if (devicesRes.status === "fulfilled") audioDevices = devicesRes.value?.devices || [];
    if (speakersRes.status === "fulfilled") {
      ttsVoices = (speakersRes.value?.available || []).map((v) => (typeof v === "string" ? v : v.name));
    }
    if (configRes.status === "rejected") {
      container.innerHTML = "";
      container.appendChild(el("div", { class: "card" }, el("div", { class: "card-body bad" }, `Ошибка: ${configRes.reason?.message}`)));
      return;
    }
    const config = configRes.value;
    const ctx = { audioDevices, ttsVoices };
    container.innerHTML = "";

    const cardGrid = el("div", { class: "card-grid" });
    SCHEMA.forEach((group) => {
      const sectionData = getNested(config, group.section) || {};
      const grid = el("div", { class: "field-grid" });

      group.fields.forEach((field) => {
        const value = sectionData[field.key];
        const isWide = field.type === "textarea" || field.type === "csv_array" ||
          (field.type === "text" && String(value ?? "").length > 40);
        const row = renderFieldRow(field, value, (f, st) =>
          fieldInput(f, value, (v) => saveField(group.section, field.key, v, st), ctx)
        );
        if (isWide) row.classList.add("field-wide");
        grid.appendChild(row);
      });

      const card = el("section", { class: "card" }, [
        el("div", { class: "card-header" }, [
          el("span", { class: "card-title" }, group.title),
          el("span", { class: "caps mono dim" }, group.section),
        ]),
        el("div", { class: "card-body" }, [grid]),
      ]);
      const hasTextarea = group.fields.some((f) => f.type === "textarea");
      if (hasTextarea) card.classList.add("card-full");
      cardGrid.appendChild(card);
    });
    container.appendChild(cardGrid);

    container.appendChild(el("div", { class: "muted", style: "font-size:12px; padding:8px 0" }, [
      el("span", null, "Модели, голос, wake-word → "),
      el("a", { href: "#/models", style: "color:var(--accent)" }, "Модели"),
      el("span", null, " · Системный промт и персонаж → "),
      el("a", { href: "#/persona", style: "color:var(--accent)" }, "Личность агента"),
    ]));
  }

  renderConfig();
  return () => {};
}

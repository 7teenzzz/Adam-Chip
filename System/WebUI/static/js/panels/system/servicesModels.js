import { api } from "../../api.js";
import { toast } from "../../widgets/toast.js";

// Field types: text | number | bool | select | textarea | int | float | string
//   source: "config" | "tuning"
//   section: dotted path for config (e.g. "services.llm")
//   tuningSectionPath: tuning group key (e.g. "llm")
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
        hint: "2–4 рекомендуется · меньше = быстрее" },
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
        hint: "1.0 = нормально · 1.25 = живее (рекомендуется) · 1.5 = быстро" },
      { key: "volume",           label: "Громкость голоса Адама", type: "float", min: 0, max: 2, step: 0.05,
        hint: "0.0 = тишина · 1.0 = норма · 2.0 = максимум (с возможным клипированием). Персональный волюм Адама — применяется поверх системной громкости Jetson" },
    ],
  },

  // ── TTS config ───────────────────────────────────────────────────────────────
  {
    source: "config", section: "services.tts", title: "TTS · Silero",
    fields: [
      { key: "base_url", label: "Адрес службы TTS", type: "text",
        hint: "http://127.0.0.1:8082" },
      { key: "output_device", label: "Аудиовыход (ALSA)", type: "text",
        hint: "plughw:1,3 = HDMI 0 · default = PulseAudio" },
      { key: "speaker", label: "Диктор (config)", type: "text",
        hint: "aidar · baya · kseniya · xenia · eugene · random · конфигурационное значение; runtime-значение выше" },
      { key: "timeout_sec", label: "Таймаут (с)", type: "number" },
    ],
  },

  // ── TTS filler («Хм...») ─────────────────────────────────────────────────────
  {
    source: "config", section: "services.tts", title: "TTS · Филлер (междометия)",
    fields: [
      { key: "filler_enabled", label: "Включить междометия", type: "bool",
        hint: "если LLM долго думает — Адам произносит короткое «Хм...» вместо тишины" },
      { key: "filler_phrase", label: "Фраза", type: "text",
        hint: "что произносить · например «Хм...», «Ух», «Эээ»" },
      { key: "filler_delay_ms", label: "Задержка LLM (мс)", type: "number",
        min: 0, max: 5000, step: 50,
        hint: "если ответ LLM начался быстрее этой задержки — филлер не звучит. 800 = норма" },
      { key: "filler_probability", label: "Вероятность (0..1)", type: "number",
        min: 0, max: 1, step: 0.05,
        hint: "0.30 = в среднем 1 из 3 ходов · 0.0 = выключено de facto · 1.0 = всегда (старое поведение). Не привязано к таймеру — независимый бросок на каждый ход" },
    ],
  },

  // ── ASR · WhisperX ───────────────────────────────────────────────────────────
  {
    source: "config", section: "services.asr", title: "ASR · WhisperX",
    fields: [
      { key: "model", label: "Модель WhisperX", type: "select",
        choices: ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        hint: "tiny/base — быстро, точность низкая · small — баланс · medium — рекомендуется · large-v2/v3 — максимум точности, 10+ ГБ VRAM" },
      { key: "reply_window_sec", label: "Reply window — soft (с)", type: "number",
        hint: "3.75 · soft-окно после ответа Адама — зритель может говорить без wake word; если речи нет → STANDBY",
        min: 1, max: 30, step: 0.25 },
      { key: "reply_window_expired_action", label: "Reply window — действие по истечении", type: "select",
        choices: ["standby", "stop"],
        hint: "standby — возврат в ожидание wake word (микрофон работает) · stop — полностью останавливает voice loop, требует ручного запуска через /api/voice/start" },
      { key: "vad_onset", label: "VAD onset (начало речи)", type: "number",
        min: 0, max: 1, step: 0.05,
        hint: "0.1 рекомендуется для USB-webcam / ESP32 INMP441 · whisperX default 0.500 (слишком строго для шумных сред) · снизить, если речь не детектируется · ⚠ требует рестарта WhisperX-контейнера" },
      { key: "vad_offset", label: "VAD offset (конец речи)", type: "number",
        min: 0, max: 1, step: 0.05,
        hint: "0.2 рекомендуется · whisperX default 0.363 · снизить, чтобы окно речи не закрывалось на коротких паузах внутри фразы · ⚠ требует рестарта WhisperX-контейнера" },
      { key: "logprob_threshold", label: "WhisperX logprob threshold (качество сегмента)", type: "number",
        min: -5.0, max: 0.0, step: 0.1,
        hint: "−1.7 до −0.5 · avg_logprob ниже порога → сегмент отброшен как шум · −0.8 = строго (пропускает тихие/короткие) · −1.7 = мягко (принимает неуверенные сегменты) · ⚠ требует рестарта WhisperX-контейнера" },
    ],
  },

  // ── VLM config ───────────────────────────────────────────────────────────────
  {
    source: "config", section: "services.vlm", title: "VLM · описание сцены",
    fields: [
      { key: "base_url",      label: "Адрес службы VLM", type: "text",
        hint: "http://127.0.0.1:8051" },
      { key: "model",         label: "Модель VLM",       type: "text" },
      { key: "max_new_tokens", label: "Макс. токенов",   type: "number",
        hint: "80 рекомендуется для формата Scene+Engagement" },
      { key: "timeout_sec",   label: "Таймаут (с)",      type: "number",
        hint: "20 рекомендуется" },
      { key: "prompt",        label: "Промт VLM",        type: "textarea",
        hint: "инструкция для описания кадра" },
    ],
  },
];

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

// ── Service management (systemd units, /api/services/{name}/{verb}) ────────

const SERVICE_META = {
  llm: { label: "LLM (llama-server)",      unit: "adam-llm.service",           desc: "Inference на GPU, порт :8081" },
  tts: { label: "TTS (Silero)",            unit: "adam-tts-silero.service",    desc: "Синтез речи, порт :8082" },
  asr: { label: "ASR (WhisperX)",          unit: "adam-asr-whisperx.service",  desc: "Распознавание речи, порт :8095" },
  vlm: { label: "VLM (Cosmos-Reason2-2B)", unit: "adam-vlm.service",           desc: "Описание сцены, порт :8051" },
};

function dot(kind) {
  return el("span", { class: `dot ${kind}` });
}

function buildServiceCard(name, meta) {
  let busy = false;

  const statusDot  = dot("muted");
  const statusText = el("span", { class: "muted", text: "загрузка…" });

  async function action(verb) {
    if (busy) return;
    busy = true;
    btnStart.disabled = true;
    btnStop.disabled  = true;
    btnRestart.disabled = true;
    statusText.textContent = verb === "start" ? "запуск…" : verb === "stop" ? "остановка…" : "перезапуск…";
    try {
      await api.post(`/api/services/${name}/${verb}`);
      toast(`${meta.label}: ${verb}`, "ok");
    } catch (err) {
      toast(`${meta.label}: ${err.message || err}`, "error");
    } finally {
      busy = false;
      await refresh();
    }
  }

  const btnStart   = el("button", { class: "btn btn-sm",          onclick: () => action("start")   }, "▶ Start");
  const btnStop    = el("button", { class: "btn btn-sm btn-danger", onclick: () => action("stop")    }, "■ Stop");
  const btnRestart = el("button", { class: "btn btn-sm",           onclick: () => action("restart") }, "↺ Restart");

  async function refresh() {
    try {
      const [svcData, statusData] = await Promise.all([
        api.get("/api/services"),
        api.get("/api/agent/status"),
      ]);
      const svc    = (svcData.services || {})[name] || {};
      const active = !!svc.active;

      // HTTP health for dot color (same logic as main.js kindFromHealth)
      const health = ((statusData.services || {})[name]) || {};
      let dotKind = "muted";
      if (health.ok === true)       dotKind = "ok";
      else if (health.loading)      dotKind = "warn";
      else if (health.ok === false) dotKind = "bad";

      statusDot.className    = `dot ${dotKind}`;
      statusText.textContent = health.ok === true ? "running"
                             : health.loading     ? "loading"
                             : active             ? "active (no probe)"
                             : "inactive";

      btnStart.disabled   = active || busy;
      btnStop.disabled    = !active || busy;
      btnRestart.disabled = !active || busy;
    } catch {
      statusDot.className    = "dot bad";
      statusText.textContent = "нет связи";
    }
  }

  const card = el("div", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("div", { class: "row", style: "gap:8px;align-items:center" }, [
        statusDot,
        el("span", { class: "card-title", text: meta.label }),
        statusText,
      ]),
    ]),
    el("div", { class: "card-body" }, [
      el("div", { class: "muted", style: "margin-bottom:10px;font-size:12px", text: meta.unit }),
      el("div", { class: "muted", style: "margin-bottom:12px", text: meta.desc }),
      el("div", { class: "row", style: "gap:8px" }, [btnStart, btnStop, btnRestart]),
    ]),
  ]);

  return { card, refresh };
}

// ── Field input + save helpers (verbatim from settings.js) ─────────────────

function fieldInput(field, value, onChange) {
  const type = field.type;

  if (type === "bool") {
    const select = el("select", { class: "select" }, [
      el("option", { value: "true",  selected: value === true  ? "selected" : null }, "включено"),
      el("option", { value: "false", selected: value === false ? "selected" : null }, "выключено"),
    ]);
    select.addEventListener("change", () => onChange(select.value === "true"));
    return select;
  }

  if (type === "select") {
    const select = el("select", { class: "select" });
    (field.choices || []).forEach((c) => {
      const opt = el("option", { value: c, selected: c === (value ?? "") ? "selected" : null });
      opt.textContent = c;
      select.appendChild(opt);
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

function buildModelCards(config, tuning) {
  const cardGrid = el("div", { class: "card-grid" });

  SCHEMA.forEach((group) => {
    const sectionData = group.source === "config"
      ? (getNested(config, group.section) || {})
      : (getNested(tuning, group.tuningSectionPath) || {});

    const grid = el("div", { class: "field-grid" });

    group.fields.forEach((field) => {
      const value = sectionData[field.key];
      const isWide = field.type === "textarea";

      const row = renderFieldRow(field, value, (f, st) => {
        if (group.source === "config") {
          return fieldInput(f, value, (v) => saveConfigField(group.section, field.key, v, st));
        }
        return fieldInput(f, value, (v) => saveTuningField(group.tuningSectionPath, field.key, v, st));
      });
      if (isWide) row.classList.add("field-wide");
      grid.appendChild(row);
    });

    const badge = group.source === "config"
      ? el("span", { class: "caps mono dim" }, group.section)
      : el("span", { class: "caps mono", style: "color:var(--accent-dim, var(--accent)); opacity:0.55" }, `tuning:${group.tuningSectionPath}`);

    const card = el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, group.title),
        badge,
      ]),
      el("div", { class: "card-body" }, [grid]),
    ]);
    const hasTextarea = group.fields.some((f) => f.type === "textarea");
    if (hasTextarea) card.classList.add("card-full");
    cardGrid.appendChild(card);
  });

  return cardGrid;
}

// ── Mount ────────────────────────────────────────────────────────────────

export function mount(target) {
  const disposables = [];

  const root = el("div", { class: "col" });
  target.appendChild(root);

  const serviceCards = Object.entries(SERVICE_META).map(([name, meta]) =>
    buildServiceCard(name, meta)
  );

  const refreshBtn = el("button", { class: "btn btn-sm", style: "margin-bottom:16px" }, "↺ Обновить");

  async function refreshAll() {
    await Promise.all(serviceCards.map((c) => c.refresh()));
  }

  refreshBtn.addEventListener("click", refreshAll);

  root.appendChild(
    el("div", { class: "panel-header" }, [
      el("h2", { class: "panel-title" }, "Сервисы и модели"),
      refreshBtn,
    ])
  );

  const serviceGrid = el("div", { class: "card-grid" });
  serviceCards.forEach((c) => serviceGrid.appendChild(c.card));
  root.appendChild(serviceGrid);

  root.appendChild(el("div", { class: "caps", style: "margin-top:16px" }, "Модели и параметры"));
  const modelsContainer = el("div", { class: "col" });
  root.appendChild(modelsContainer);

  async function loadModelCards() {
    modelsContainer.innerHTML = "";
    modelsContainer.appendChild(el("div", { class: "muted" }, [el("span", { class: "spinner" }), " загрузка…"]));

    const [configRes, tuningRes] = await Promise.allSettled([
      api.get("/api/config"),
      api.get("/api/tuning"),
    ]);

    if (configRes.status === "rejected" || tuningRes.status === "rejected") {
      modelsContainer.innerHTML = "";
      modelsContainer.appendChild(el("div", { class: "card" }, el("div", { class: "card-body bad" },
        `Ошибка загрузки моделей: ${(configRes.reason || tuningRes.reason)?.message}`)));
      return;
    }

    modelsContainer.innerHTML = "";
    modelsContainer.appendChild(buildModelCards(configRes.value, tuningRes.value));
  }

  refreshAll();
  loadModelCards();
  const interval = setInterval(refreshAll, 5000);
  disposables.push(() => clearInterval(interval));

  return function teardown() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
  };
}

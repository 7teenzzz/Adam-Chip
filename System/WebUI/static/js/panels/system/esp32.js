// Panel: #/system/esp32
// ESP32-S3 subsystem page — three sub-tabs:
//   Общие настройки — ESP addresses + mcu/safety/sounds config (editable, saveConfigField)
//   Моторный слой   — manual PCA9685 PWM channel control (0-15, value 0-4095)
//   Сенсорный слой  — read-only camera/mic/light/PIR module status

import { api } from "../../api.js";
import { toast } from "../../widgets/toast.js";

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

// ── Tab bar (pattern from panels/agent/memory.js) ───────────────────────────────

function buildTabBar(tabs, onChange) {
  const buttons = tabs.map((tab) => {
    const btn = el("button", {
      class: "btn btn-ghost",
      style: "font-size:13px; border-radius:0; padding:8px 16px; border-bottom:2px solid transparent; background:none; cursor:pointer",
      text: tab.label,
      onclick: () => {
        buttons.forEach((b, i) => {
          const isActive = i === tabs.indexOf(tab);
          b.style.borderBottomColor = isActive ? "var(--accent)" : "transparent";
          b.style.color = isActive ? "var(--accent)" : "";
        });
        onChange(tab.id);
      },
    });
    return btn;
  });

  buttons[0].style.borderBottomColor = "var(--accent)";
  buttons[0].style.color = "var(--accent)";

  return el("div", {
    class: "row",
    style: "border-bottom:1px solid var(--border); gap:0; margin-bottom:16px",
  }, buttons);
}

// ── Address row (from panels/subsystem.js) ──────────────────────────────────────

function addrRow(label, value) {
  if (!value) return null;
  return el("div", {
    style: "display:flex; justify-content:space-between; align-items:center; padding:5px 0; border-bottom:1px solid var(--bg-3); font-size:12px",
  }, [
    el("span", { class: "caps", style: "color:var(--muted)" }, label),
    el("a", {
      href: value.startsWith("http") ? value : "#",
      target: "_blank",
      rel: "noopener",
      class: "mono",
      style: "color:var(--accent); text-decoration:none; word-break:break-all",
    }, value),
  ]);
}

// ── Field row + input (subset of panels/settings.js — text/number/bool only) ───

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

function fieldInput(field, value, onChange) {
  if (field.type === "bool") {
    const select = el("select", { class: "select" }, [
      el("option", { value: "true",  selected: value === true  ? "selected" : null }, "включено"),
      el("option", { value: "false", selected: value === false ? "selected" : null }, "выключено"),
    ]);
    select.addEventListener("change", () => onChange(select.value === "true"));
    return select;
  }

  const isNum = field.type === "number";
  const input = el("input", { class: "input", type: isNum ? "number" : "text", step: isNum ? "any" : null });
  input.value = value ?? "";
  input.addEventListener("change", () => {
    if (isNum) {
      const v = parseFloat(input.value);
      if (Number.isNaN(v)) { toast(`${field.label}: ожидалось число`, "bad"); return; }
      onChange(v);
    } else {
      onChange(input.value);
    }
  });
  return input;
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

// ── Общие настройки (3.3.1) ──────────────────────────────────────────────────

const GENERAL_GROUPS = [
  {
    section: "mcu", title: "Модуль ESP32",
    fields: [
      { key: "base_url",         label: "Адрес ESP32",          type: "text", hint: "http://10.10.10.171" },
      { key: "speaker_url",      label: "Адрес динамика ESP32", type: "text" },
      { key: "timeout_sec",      label: "Таймаут (с)",          type: "number", hint: "1 рекомендуется — иначе блокирует диалог" },
      { key: "idle_scene",       label: "Сцена простоя",        type: "text" },
      { key: "flora_timeout_sec", label: "Таймаут флоры (с)",   type: "number", hint: "3 — для set_flora_state, отдельно от timeout_sec" },
    ],
  },
  {
    section: "safety", title: "Безопасность и моторика",
    fields: [
      { key: "half_duplex_mute",          label: "Mute микрофона во время TTS", type: "bool", hint: "предотвращает самоответ агента" },
      { key: "motor_default_duration_ms", label: "Длительность мотора (мс)",    type: "number", hint: "900 рекомендуется" },
      { key: "motor_max_duration_ms",     label: "Макс. длительность (мс)",     type: "number", hint: "не более 2500" },
      { key: "motor_cooldown_ms",         label: "Охлаждение мотора (мс)",      type: "number" },
    ],
  },
  {
    section: "sounds", title: "Системные звуки",
    fields: [
      { key: "enabled",             label: "Включены",                  type: "bool" },
      { key: "success_path",        label: "Звук успеха (путь к файлу)", type: "text" },
      { key: "local_output_device", label: "Устройство вывода звуков",   type: "text" },
    ],
  },
];

function renderGeneral(container, esp, config) {
  container.innerHTML = "";

  const addrCard = el("section", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Адреса ESP32")),
    el("div", { class: "card-body" }, [
      addrRow("HTTP API", esp?.base_url),
      addrRow("Камера (MJPEG)", esp?.camera_stream_url),
      addrRow("Микрофон (поток)", esp?.mic_stream_url),
      addrRow("Динамик", esp?.speaker_url),
    ]),
  ]);

  const cardGrid = el("div", { class: "card-grid" });
  GENERAL_GROUPS.forEach((group) => {
    const sectionData = config?.[group.section] || {};
    const grid = el("div", { class: "field-grid" });
    group.fields.forEach((field) => {
      const value = sectionData[field.key];
      const row = renderFieldRow(field, value, (f, status) =>
        fieldInput(f, value, (v) => saveConfigField(group.section, field.key, v, status)));
      grid.appendChild(row);
    });
    cardGrid.appendChild(el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, group.title),
        el("span", { class: "caps mono dim" }, group.section),
      ]),
      el("div", { class: "card-body" }, [grid]),
    ]));
  });

  container.appendChild(addrCard);
  container.appendChild(cardGrid);
}

// ── Моторный слой (3.3.2) ────────────────────────────────────────────────────

function pwmChannelRow(channel, bounds) {
  const status = el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });
  const input = el("input", {
    class: "input", type: "number",
    min: bounds.value_min, max: bounds.value_max, step: "1",
    style: "width:90px",
  });
  input.value = "0";

  const applyBtn = el("button", { class: "btn btn-ghost", style: "padding:4px 12px" }, "Применить");
  applyBtn.addEventListener("click", async () => {
    let value = parseInt(input.value, 10);
    if (Number.isNaN(value)) { toast(`Канал ${channel}: ожидалось число`, "bad"); return; }
    value = Math.max(bounds.value_min, Math.min(bounds.value_max, value));
    input.value = String(value);
    status.classList.remove("ok", "warn", "bad");
    status.classList.add("warn");
    status.textContent = "…";
    try {
      await api.post("/api/ui/pca/channel", { channel, mode: "pwm", value });
      status.classList.remove("warn");
      status.classList.add("ok");
      status.textContent = "ok";
      setTimeout(() => { status.textContent = ""; status.classList.remove("ok"); }, 2000);
    } catch (e) {
      status.classList.remove("warn");
      status.classList.add("bad");
      status.textContent = "ошибка";
      toast(`Канал ${channel}: ${e.message}`, "bad", 5000);
    }
  });

  return el("div", {
    style: "display:flex; align-items:center; gap:10px; padding:5px 0; border-bottom:1px solid var(--bg-3)",
  }, [
    el("span", { class: "mono", style: "min-width:64px; color:var(--muted)" }, `канал ${channel}`),
    input,
    applyBtn,
    status,
  ]);
}

function renderMotor(container, mcuConfig) {
  container.innerHTML = "";
  const channels = mcuConfig?.channels || {};
  const bounds = {
    min: channels.min ?? 0,
    max: channels.max ?? 15,
    value_min: channels.value_min ?? 0,
    value_max: channels.value_max ?? 4095,
  };

  const rows = el("div", { class: "col", style: "gap:0" });
  for (let ch = bounds.min; ch <= bounds.max; ch++) {
    rows.appendChild(pwmChannelRow(ch, bounds));
  }

  container.appendChild(el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Ручное управление PWM (PCA9685)"),
      el("span", { class: "caps mono dim" }, `0-${bounds.value_max}`),
    ]),
    el("div", { class: "card-body" }, [
      el("p", { style: "color:var(--muted); font-size:12px; margin:0 0 8px" },
        "Значение применяется немедленно через POST /api/ui/pca/channel. Backend ограничивает канал и значение по mcu.channels."),
      rows,
    ]),
  ]));
}

// ── Сенсорный слой (3.3.3) ───────────────────────────────────────────────────

const SENSOR_LABELS = {
  cam:     "Камера (OV5640)",
  mic:     "Микрофон (INMP441)",
  temt600: "Датчик света (TEMT6000)",
  pir:     "Датчик движения (PIR)",
};

function sensorRow(label, value) {
  const known = value === true || value === false;
  const kind = !known ? "warn" : value ? "ok" : "bad";
  const colors = { ok: "var(--ok, #4caf50)", bad: "var(--bad, #f44336)", warn: "var(--warn, #ff9800)" };
  const text = !known ? "н/д" : value ? "активен" : "нет сигнала";
  return el("div", {
    style: "display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--bg-3)",
  }, [
    el("span", {
      style: `display:inline-block; width:8px; height:8px; border-radius:50%; background:${colors[kind]}; flex-shrink:0`,
    }),
    el("span", { style: "font-size:13px" }, label),
    el("span", { class: "dim", style: "font-size:11px; margin-left:auto" }, text),
  ]);
}

function renderSensors(container, modules, esp) {
  container.innerHTML = "";
  const grid = el("div", { class: "col", style: "gap:0" });
  Object.entries(SENSOR_LABELS).forEach(([key, label]) => {
    grid.appendChild(sensorRow(label, modules?.[key]));
  });

  container.appendChild(el("section", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Статус сенсоров ESP32")),
    el("div", { class: "card-body" }, [
      grid,
      addrRow("Поток камеры", esp?.camera_stream_url),
      addrRow("Поток микрофона", esp?.mic_stream_url),
    ]),
  ]));
}

// ── Main mount ────────────────────────────────────────────────────────────────

export function mount(target) {
  const disposables = [];

  const container = el("div", { class: "col", style: "gap:0" });
  target.appendChild(container);

  const generalContent = el("div", { class: "col", style: "gap:12px; display:block" });
  const motorContent   = el("div", { class: "col", style: "gap:12px; display:none" });
  const sensorContent  = el("div", { class: "col", style: "gap:12px; display:none" });

  const tabBar = buildTabBar(
    [
      { id: "general", label: "Общие настройки" },
      { id: "motor",   label: "Моторный слой" },
      { id: "sensors", label: "Сенсорный слой" },
    ],
    (id) => {
      generalContent.style.display = id === "general" ? "block" : "none";
      motorContent.style.display   = id === "motor"   ? "block" : "none";
      sensorContent.style.display  = id === "sensors" ? "block" : "none";
    }
  );

  container.appendChild(tabBar);
  container.appendChild(generalContent);
  container.appendChild(motorContent);
  container.appendChild(sensorContent);

  async function renderAll() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }

    generalContent.innerHTML = "";
    generalContent.appendChild(el("div", { class: "muted", style: "font-size:12px; padding:12px 0", text: "Загрузка…" }));

    let status, config;
    try {
      [status, config] = await Promise.all([
        api.get("/api/ui/status"),
        api.get("/api/config"),
      ]);
    } catch (e) {
      generalContent.innerHTML = "";
      generalContent.appendChild(el("div", {
        class: "muted", style: "font-size:12px; padding:12px 0",
        text: "Ошибка загрузки: " + e.message,
      }));
      return;
    }

    renderGeneral(generalContent, status?.esp, config);
    renderMotor(motorContent, config?.mcu);
    renderSensors(sensorContent, status?.modules, status?.esp);
  }

  renderAll();

  return function teardown() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
  };
}

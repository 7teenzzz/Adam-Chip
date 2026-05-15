import { api, subscribeEvents } from "./api.js";
import { state } from "./state.js";
import { router } from "./router.js";
import { toast } from "./widgets/toast.js";
import { statusDot, kindFromHealth } from "./widgets/statusDot.js";

const MODES = ["maintenance", "idle", "listening", "performance", "exhibition"];

function el(tag, attrs, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null || c === false) return;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return node;
}

function buildTopbar() {
  const brand = el("div", { class: "brand" }, [
    el("span", { class: "brand-mark" }, "A"),
    el("span", { class: "brand-name" }, "ADAM CHIP"),
  ]);

  const onlineDot = statusDot("warn", "online");
  onlineDot.id = "topbar-online-dot";
  const services = el("div", { id: "topbar-services", style: "display:flex; align-items:center; gap:0" }, [
    el("div", { id: "topbar-svc-left",  style: "display:flex; align-items:center; gap:12px" }),
    el("span", { class: "topbar-svc-sep" }),
    el("div", { id: "topbar-svc-right", style: "display:flex; align-items:center; gap:12px" }),
  ]);

  const modeSelect = el("select", {
    class: "select",
    id: "mode-select",
    style: "width:170px",
    onchange: async (ev) => {
      const mode = ev.target.value;
      try {
        await api.post("/api/agent/mode", { mode });
        toast(`Режим: ${mode}`, "ok");
      } catch (e) {
        toast(`Ошибка смены режима: ${e.message}`, "bad", 5000);
        const cur = state.get("status")?.agent?.mode || "maintenance";
        ev.target.value = cur;
      }
    },
  }, MODES.map((m) => {
    const opt = el("option", { value: m }, m);
    return opt;
  }));

  const stopBtn = el("button", {
    class: "btn",
    title: "Прервать речь и моторику (Esc)",
    onclick: async () => {
      try { await api.post("/api/agent/stop", {}); toast("Остановлено", "ok"); }
      catch (e) { toast(e.message, "bad"); }
    },
  }, "Стоп");

  return el("header", { class: "topbar" }, [
    brand,
    el("div", { class: "topbar-status" }, [onlineDot, services]),
    el("div", { class: "topbar-actions" }, [modeSelect, stopBtn]),
  ]);
}

const NAV_STRUCTURE = [
  { key: "chat", label: "Чат" },
  {
    group: "Настройки",
    id: "config",
    children: [
      { sectionLabel: "Система" },
      { key: "settings",   label: "Настройки" },
      { key: "models",     label: "Модели" },
      { key: "subsystem",  label: "Подсистема" },
      { key: "services",   label: "Сервисы" },
      { separator: true },
      { key: "persona",    label: "Личность агента" },
    ],
  },
  { key: "metrics", label: "Метрики" },
  { key: "logs",    label: "Логи" },
];

function navLink(key, label, indent = false) {
  return el("a", {
    class: "nav-link",
    href: `#/${key}`,
    "data-route": key,
    style: indent ? "padding-left:24px" : "",
  }, [
    el("span", { class: "mono", style: "color:var(--accent)" }, "▸"),
    el("span", null, label),
  ]);
}

function buildNav() {
  const nav = el("nav", { class: "nav" });

  NAV_STRUCTURE.forEach((item) => {
    if (item.key) {
      nav.appendChild(navLink(item.key, item.label));
      return;
    }
    if (!item.group) return;

    const storageKey = `navGroup_${item.id}`;
    const isOpen = localStorage.getItem(storageKey) !== "false";

    const body = el("div", {
      id: `nav-group-${item.id}`,
      style: `display:${isOpen ? "flex" : "none"}; flex-direction:column`,
    });

    item.children.forEach((child) => {
      if (child.sectionLabel) {
        body.appendChild(el("div", {
          style: "padding:6px 12px 2px 16px; font-size:10px; letter-spacing:0.1em; color:var(--muted); opacity:0.55; text-transform:uppercase",
        }, child.sectionLabel));
      } else if (child.separator) {
        body.appendChild(el("div", { style: "height:1px; background:var(--line); margin:4px 8px" }));
      } else if (child.key) {
        body.appendChild(navLink(child.key, child.label, true));
      }
    });

    const arrowSpan = el("span", { class: "mono", style: "color:var(--accent); width:14px; text-align:center" }, isOpen ? "▾" : "▸");
    const header = el("button", {
      class: "nav-link",
      style: "width:100%; text-align:left; background:none; border:none; cursor:pointer; display:flex; align-items:center; gap:8px; font:inherit",
      onclick: () => {
        const open = body.style.display !== "none";
        body.style.display = open ? "none" : "flex";
        arrowSpan.textContent = open ? "▸" : "▾";
        localStorage.setItem(storageKey, String(!open));
      },
    }, [arrowSpan, el("span", null, item.group)]);

    nav.appendChild(header);
    nav.appendChild(body);
  });

  return nav;
}

function buildSide() {
  return el("aside", { class: "side", id: "side" }, [
    el("div", { class: "card" }, [
      el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Латентность")),
      el("div", { class: "card-body", id: "side-latency", style: "padding:12px 14px" }, "—"),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Live events")),
      el("div", { class: "card-body", id: "side-events", style: "max-height:48vh; overflow-y:auto; padding:8px 12px" }),
    ]),
  ]);
}

function fmtMs(value) {
  if (value == null) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(2)} с`;
  return `${Math.round(value)} мс`;
}

function paintLatency(status) {
  const root = document.getElementById("side-latency");
  if (!root) return;
  const lat = status?.agent?.latency_ms || {};
  root.innerHTML = "";
  const rows = [
    ["LLM", lat.llm],
    ["TTS", lat.tts],
    ["ASR", lat.asr],
    ["VLM", lat.vlm],
  ];
  rows.forEach(([label, value]) => {
    const row = el("div", {
      style: "display:flex; justify-content:space-between; align-items:center; padding:5px 0; border-bottom:1px solid var(--bg-3); font-size:13px",
    }, [
      el("span", { class: "caps", style: "color:var(--muted)" }, label),
      el("span", { class: "mono", style: `color:${value == null ? "var(--dim)" : "var(--accent)"}` }, fmtMs(value)),
    ]);
    root.appendChild(row);
  });
}

function overallKind(services, mcu) {
  const healths = [...Object.values(services || {}), mcu].filter(Boolean);
  if (!healths.length) return "warn";
  if (healths.every((h) => h?.ok === true)) return "ok";
  if (healths.some((h) => h?.loading === true)) return "amber";
  if (healths.some((h) => h?.ok === false)) return "bad";
  return "warn";
}

function paintTopbarStatus(status) {
  const root = document.getElementById("topbar-svc-left");
  if (!root) return;
  root.innerHTML = "";
  const services = status?.services || {};
  const order = [
    ["llm", "LLM"],
    ["tts", "TTS"],
    ["asr", "ASR"],
    ["vlm", "VLM"],
  ];
  order.forEach(([key, label]) => {
    const h = services[key];
    const detail = h?.detail || h?.error || (h?.ok ? "ok" : "—");
    root.appendChild(statusDot(kindFromHealth(h), label, `${label}: ${detail}`));
  });

  const onlineWrap = document.getElementById("topbar-online-dot");
  if (onlineWrap) {
    const mcu = status?.mcu;
    const dot = onlineWrap.querySelector(".dot");
    if (dot) dot.className = `dot ${overallKind(services, mcu)}`;
  }
}

function paintEspModules(uiData) {
  const svc = document.getElementById("topbar-svc-right");
  if (!svc) return;
  svc.innerHTML = "";
  if (!uiData) return;

  const mod = uiData.modules || {};
  const vl  = uiData.voice_loop || {};

  function modKind(ok) {
    if (ok === undefined || ok === null) return "";
    return ok ? "ok" : "bad";
  }

  function micKind() {
    if (mod.mic === undefined) return "";
    if (!mod.mic) return "bad";
    return vl.esp_mic_fallback ? "warn" : "ok";
  }

  function micTitle() {
    if (!mod.mic) return "E-Mic: аппаратная ошибка";
    if (vl.esp_mic_fallback) return "E-Mic: ESP32 недоступен, используется pulse";
    return "E-Mic: INMP441 активен";
  }

  const dots = [
    statusDot(modKind(mod.cam),     "E-Cam",   `E-Cam: ${mod.cam ? "ok" : "error"}`),
    statusDot(micKind(),            "E-Mic",   micTitle()),
    statusDot(modKind(mod.pca9685), "Motility",`Motility: ${mod.pca9685 ? "ok" : "error"}`),
    statusDot(modKind(mod.temt600), "Light",   `Light: ${mod.temt600 ? "ok" : "no signal"}`),
    statusDot(modKind(mod.pir),     "Motion",  `Motion: ${mod.pir ? "ok" : "no signal"}`),
  ];
  dots.forEach((d) => svc.appendChild(d));
}

function paintMode(status) {
  const select = document.getElementById("mode-select");
  if (!select) return;
  const mode = status?.agent?.mode;
  if (mode && select.value !== mode) select.value = mode;
}

function paintScene(status) {
  const root = document.getElementById("side-scene");
  if (!root) return;
  const sc = status?.scene_cache;
  if (!sc || !sc.text) {
    root.textContent = "Сцена не описана.";
    return;
  }
  root.innerHTML = "";
  root.appendChild(el("div", { style: "color:var(--text); margin-bottom:6px" }, sc.text));
  root.appendChild(el("div", { class: "caps" }, sc.stale ? "устарело" : "актуально"));
}

const SIDE_EVENTS = new Set([
  // ── Система ─────────────────────────────
  "orchestrator_started",
  "voice_loop_started",
  "voice_loop_stopped",
  "voice_loop_error",
  "mode_changed",
  "startup_services_timeout",
  // ── ESP32 / MCU ──────────────────────────
  "esp32_health_error",
  "esp32_health_poll_failed",
  "esp32_audio_health",
  "esp32_audio_health_auto_switch",
  "esp32_mic_fallback_start",
  "esp32_mic_restored",
  "esp32_mic_stream_opened",
  "esp32_mic_wav_header",
  // ── Pipeline nodes ───────────────────────
  "wake_word_detected",     // 1. wake word
  "asr_final",              // 2. ASR
  "asr_wake_only",          // 2. ASR (только wake word)
  "llm_thinking_started",   // 3. LLM
  "llm_thinking_finished",  // 3. LLM
  "llm_error",              // 3. LLM error
  "tts_started",            // 4. TTS
  "tts_finished",           // 4. TTS
  "adam_reply",             // 5. ответ
  // ── Исключения пайплайна ─────────────────
  "wake_silence_timeout",
  "reply_window_expired",
  "asr_no_reply_standby",
]);

function appendEventToSide(ev) {
  if (!SIDE_EVENTS.has(ev.type)) return;
  const root = document.getElementById("side-events");
  if (!root) return;
  const ts = (ev.ts || "").slice(11, 19);
  const line = el("div", {
    class: "fade-in",
    style: "font-family:var(--font-mono); font-size:11px; padding:4px 0; border-bottom:1px solid var(--bg-3); display:grid; grid-template-columns:48px 110px 1fr; gap:8px; align-items:start",
  }, [
    el("span", { class: "dim" }, ts),
    el("span", { style: "color:var(--accent)" }, ev.type || "?"),
    el("span", { class: "muted", style: "white-space:pre-wrap; word-break:break-word" }, summarisePayload(ev.payload)),
  ]);
  root.prepend(line);
  while (root.children.length > 80) root.removeChild(root.lastChild);
}

function summarisePayload(payload) {
  if (!payload || typeof payload !== "object") return String(payload ?? "");
  if (payload.text) return String(payload.text).slice(0, 160);
  if (payload.error) return `! ${payload.error}`;
  if (payload.mode) return `mode=${payload.mode}`;
  const keys = Object.keys(payload).slice(0, 4);
  return keys.map((k) => `${k}=${typeof payload[k] === "object" ? "{…}" : payload[k]}`).join(" ");
}

async function refreshStatus() {
  try {
    const status = await api.get("/api/agent/status");
    state.set("status", status);
    paintTopbarStatus(status);
    paintMode(status);
    paintScene(status);
    paintLatency(status);
  } catch (e) {
    console.error("status refresh failed", e);
  }
}

let _espModulesData = null;

async function refreshEspModules() {
  try {
    const data = await api.get("/api/ui/status");
    _espModulesData = data;
    paintEspModules(data);
  } catch (_) {
    paintEspModules(null);
  }
}

function bootstrap() {
  try {
    const boot = document.getElementById("boot");
    if (boot) boot.remove();

    const root = el("div", { id: "root" });
    root.appendChild(buildTopbar());
    const app = el("div", { class: "app" });
    app.appendChild(buildNav());
    const main = el("main", { class: "main", id: "main" });
    app.appendChild(main);
    app.appendChild(buildSide());
    root.appendChild(app);
    document.body.appendChild(root);

    router.init(main);

    state.subscribe("status", () => {});

    refreshStatus();
    setInterval(refreshStatus, 4000);

    refreshEspModules();
    setInterval(refreshEspModules, 8000);

    subscribeEvents(
      (event) => {
        appendEventToSide(event);
        state.patch("last_events", { last: event });
        if (["mode_changed", "tts_finished", "voice_loop_started", "voice_loop_stopped", "config_patched"].includes(event.type)) {
          refreshStatus();
        }
      },
      () => { /* reconnect handled inside subscribeEvents */ },
    );

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") {
        api.post("/api/agent/stop", {}).then(() => toast("Остановлено")).catch(() => {});
      }
    });
  } catch (err) {
    console.error("bootstrap failed:", err);
    const node = document.getElementById("boot-error");
    if (node) {
      node.style.display = "block";
      node.textContent = `[bootstrap] ${err.message}\n${err.stack || ""}`;
    } else {
      document.body.insertAdjacentHTML(
        "afterbegin",
        `<pre style="padding:24px;color:#ff6363;font-family:monospace;white-space:pre-wrap">[bootstrap] ${err.message}\n${err.stack || ""}</pre>`,
      );
    }
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}

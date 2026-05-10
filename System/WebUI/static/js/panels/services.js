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

const SERVICE_META = {
  llm: { label: "LLM (llama-server)",   unit: "adam-llm.service",           desc: "Inference на GPU, порт :8081" },
  tts: { label: "TTS (Silero)",          unit: "adam-tts-silero.service",   desc: "Синтез речи, порт :8082" },
  asr: { label: "ASR (speaches)",        unit: "adam-asr-speaches.service", desc: "Распознавание речи, порт :8083" },
};

// ── VLM Docker card (не systemd, управляется через Docker API) ──────────

function buildVlmCard() {
  let busy = false;
  const statusDot  = el("span", { class: "dot muted" });
  const statusText = el("span", { class: "muted", text: "загрузка…" });
  const btnStart   = el("button", { class: "btn btn-sm",           onclick: () => action("start")   }, "▶ Start");
  const btnStop    = el("button", { class: "btn btn-sm btn-danger", onclick: () => action("stop")    }, "■ Stop");

  async function action(verb) {
    if (busy) return;
    busy = true;
    btnStart.disabled = true;
    btnStop.disabled  = true;
    statusText.textContent = verb === "start" ? "запуск…" : "остановка…";
    try {
      await api.post(`/api/live_vlm/${verb}`);
      toast(`VLM: ${verb}`, "ok");
    } catch (err) {
      toast(`VLM: ${err.message || err}`, "error");
    } finally {
      busy = false;
      await refresh();
    }
  }

  async function refresh() {
    try {
      const data = await api.get("/api/live_vlm/status");
      const running = !!data.running;
      statusDot.className  = running ? "dot ok" : "dot bad";
      statusText.textContent = running ? "running" : "stopped";
      btnStart.disabled = running || busy;
      btnStop.disabled  = !running || busy;
    } catch {
      statusDot.className = "dot bad";
      statusText.textContent = "нет связи";
    }
  }

  const card = el("div", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("div", { class: "row", style: "gap:8px;align-items:center" }, [
        statusDot,
        el("span", { class: "card-title", text: "VLM (VILA1.5-3b)" }),
        statusText,
      ]),
    ]),
    el("div", { class: "card-body" }, [
      el("div", { class: "muted", style: "margin-bottom:10px;font-size:12px", text: "adam-live-vlm (Docker)" }),
      el("div", { class: "muted", style: "margin-bottom:12px", text: "Описание сцены через камеру, порт :8084" }),
      el("div", { class: "row", style: "gap:8px" }, [btnStart, btnStop]),
    ]),
  ]);

  return { card, refresh };
}

const STATE_STYLE = {
  active:       { dot: "ok",    text: "active" },
  activating:   { dot: "warn",  text: "activating" },
  deactivating: { dot: "warn",  text: "stopping" },
  inactive:     { dot: "bad",   text: "inactive" },
  failed:       { dot: "bad",   text: "failed" },
  unknown:      { dot: "muted", text: "?" },
  error:        { dot: "bad",   text: "error" },
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
      const data = await api.get("/api/services");
      const svc  = (data.services || {})[name] || {};
      const state  = svc.state || "unknown";
      const active = !!svc.active;
      const style  = STATE_STYLE[state] || STATE_STYLE.unknown;

      statusDot.className = `dot ${style.dot}`;
      statusText.textContent = style.text;

      btnStart.disabled   = active || busy;
      btnStop.disabled    = !active || busy;
      btnRestart.disabled = !active || busy;
    } catch {
      statusDot.className = "dot bad";
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

export function mount(root) {
  const cards = Object.entries(SERVICE_META).map(([name, meta]) =>
    buildServiceCard(name, meta)
  );
  const vlmCard = buildVlmCard();

  const refreshBtn = el("button", { class: "btn btn-sm", style: "margin-bottom:16px" }, "↺ Обновить");

  async function refreshAll() {
    await Promise.all([...cards.map((c) => c.refresh()), vlmCard.refresh()]);
  }

  refreshBtn.addEventListener("click", refreshAll);

  root.appendChild(
    el("div", { class: "panel-header" }, [
      el("h2", { class: "panel-title" }, "Сервисы"),
      refreshBtn,
    ])
  );
  cards.forEach((c) => root.appendChild(c.card));
  root.appendChild(vlmCard.card);

  refreshAll();
  const interval = setInterval(refreshAll, 5000);

  return () => clearInterval(interval);
}

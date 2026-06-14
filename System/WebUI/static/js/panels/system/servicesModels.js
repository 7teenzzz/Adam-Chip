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

  refreshAll();
  const interval = setInterval(refreshAll, 5000);
  disposables.push(() => clearInterval(interval));

  return function teardown() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
  };
}

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
  llm: { label: "LLM (llama-server)",   unit: "adam-llm.service",          desc: "Inference на GPU, порт :8051" },
  tts: { label: "TTS (Silero)",          unit: "adam-tts-silero.service",   desc: "Синтез речи, порт :8090" },
  asr: { label: "ASR (Whisper)",         unit: "adam-asr-whisper.service",  desc: "Распознавание речи, порт :8095" },
};

const STATE_STYLE = {
  active:       { dot: "good",  text: "active" },
  activating:   { dot: "warn",  text: "activating" },
  deactivating: { dot: "warn",  text: "stopping" },
  inactive:     { dot: "bad",   text: "inactive" },
  failed:       { dot: "bad",   text: "failed" },
  unknown:      { dot: "muted", text: "?" },
  error:        { dot: "bad",   text: "error" },
};

function dot(kind) {
  return el("span", { class: `status-dot ${kind}` });
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

      statusDot.className = `status-dot ${style.dot}`;
      statusText.textContent = style.text;

      btnStart.disabled   = active || busy;
      btnStop.disabled    = !active || busy;
      btnRestart.disabled = !active || busy;
    } catch {
      statusDot.className = "status-dot bad";
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

  const note = el("div", { class: "card" }, [
    el("div", { class: "card-body muted", style: "font-size:12px" }, [
      el("strong", {}, "Требования: "),
      "кнопки Start/Stop используют ",
      el("code", {}, "sudo -n systemctl"),
      ". Для работы из WebUI добавь NOPASSWD-правило:",
      el("pre", { style: "margin-top:6px;font-size:11px" },
        `%i17jet ALL=(ALL) NOPASSWD: /usr/bin/systemctl start adam-*.service\n` +
        `%i17jet ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop adam-*.service\n` +
        `%i17jet ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart adam-*.service`
      ),
      "Или запусти: ",
      el("code", {}, "sudo visudo -f /etc/sudoers.d/adam-services"),
    ]),
  ]);

  const refreshBtn = el("button", { class: "btn btn-sm", style: "margin-bottom:16px" }, "↺ Обновить");

  async function refreshAll() {
    await Promise.all(cards.map((c) => c.refresh()));
  }

  refreshBtn.addEventListener("click", refreshAll);

  root.appendChild(
    el("div", { class: "panel-header" }, [
      el("h2", { class: "panel-title" }, "Сервисы"),
      refreshBtn,
    ])
  );
  cards.forEach((c) => root.appendChild(c.card));
  root.appendChild(note);

  refreshAll();
  const interval = setInterval(refreshAll, 5000);

  return () => clearInterval(interval);
}

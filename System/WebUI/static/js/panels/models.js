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

function fmtBytes(n) {
  if (n == null) return "";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let v = n;
  let u = 0;
  while (v >= 1024 && u < units.length - 1) { v /= 1024; u++; }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[u]}`;
}

async function applyPatch(section, patch, statusBadge) {
  statusBadge.classList.remove("ok", "warn", "bad");
  statusBadge.classList.add("warn");
  statusBadge.textContent = "сохранение…";
  try {
    const res = await api.patch("/api/config", { section, patch });
    statusBadge.classList.remove("warn");
    statusBadge.classList.add("ok");
    statusBadge.textContent = `обновлено · ${(res.restarted || []).join(", ") || "config"}`;
    toast(`${section}: ${JSON.stringify(patch)}`, "ok", 3000);
    return true;
  } catch (e) {
    statusBadge.classList.remove("warn");
    statusBadge.classList.add("bad");
    statusBadge.textContent = "ошибка";
    toast(`${section}: ${e.message}`, "bad", 5000);
    return false;
  }
}

function modelCard({ title, section, options, current, fields, error, statusBadgeText }) {
  const status = el("span", { class: "badge ok" }, statusBadgeText || (current ? "загружено" : "не выбрано"));
  if (error) { status.classList.remove("ok"); status.classList.add("bad"); status.textContent = "ошибка"; }
  const body = el("div", { class: "col", style: "gap:14px" });

  // Primary dropdown.
  if (options) {
    const select = el("select", { class: "select" });
    options.forEach((opt) => {
      const o = el("option", { value: opt.value || opt.name });
      o.textContent = opt.label || opt.name + (opt.size ? ` · ${fmtBytes(opt.size)}` : "");
      if ((opt.value || opt.name) === current) o.selected = true;
      select.appendChild(o);
    });
    if (!options.find((o) => (o.value || o.name) === current) && current) {
      const stub = el("option", { value: current, selected: "selected" });
      stub.textContent = `${current} (текущая)`;
      select.appendChild(stub);
    }
    select.addEventListener("change", async () => {
      const value = select.value;
      const ok = await applyPatch(section, fields.primary(value), status);
      if (!ok) select.value = current;
    });
    body.appendChild(el("label", null, [
      el("div", { class: "caps", style: "color:var(--muted); margin-bottom:4px" }, fields.primaryLabel || "Модель"),
      select,
    ]));
  }

  if (error) {
    body.appendChild(el("div", { class: "muted", style: "font-size:12px; color:var(--bad)" }, `Ошибка получения списка: ${error}`));
  }

  // Optional secondary fields (text/number).
  (fields.extra || []).forEach((f) => {
    const input = el("input", { class: "input", value: f.value ?? "", placeholder: f.placeholder || "" });
    input.addEventListener("change", async () => {
      let val = input.value;
      if (f.type === "number") {
        val = Number(val);
        if (Number.isNaN(val)) { toast(`${f.label}: ожидалось число`, "bad"); return; }
      }
      await applyPatch(section, { [f.key]: val }, status);
    });
    body.appendChild(el("label", null, [
      el("div", { class: "caps", style: "color:var(--muted); margin-bottom:4px" }, f.label),
      input,
    ]));
  });

  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, title),
      status,
    ]),
    el("div", { class: "card-body" }, body),
  ]);
}

export function mount(target) {
  const grid = el("div", { class: "grid-2", style: "gap:16px; align-items:start" });
  const refreshBtn = el("button", { class: "btn", onclick: () => render() }, "Обновить");

  target.appendChild(el("section", { class: "col" }, [
    el("div", { class: "row" }, [
      el("div", { class: "caps" }, "Выбор моделей · смена сразу применяется и пересоздаёт клиент"),
      el("span", { class: "spacer" }),
      refreshBtn,
    ]),
    grid,
  ]));

  async function render() {
    grid.innerHTML = "";
    grid.appendChild(el("div", { class: "muted" }, [el("span", { class: "spinner" }), " загрузка…"]));
    try {
      const [llm, asr, tts, vlm, config] = await Promise.all([
        api.get("/api/models/llm"),
        api.get("/api/models/asr"),
        api.get("/api/models/tts"),
        api.get("/api/models/vlm").catch((e) => ({ current: "", available: [], error: e.message })),
        api.get("/api/config"),
      ]);
      grid.innerHTML = "";

      // ---- LLM ----------------------------------------------------------
      grid.appendChild(modelCard({
        title: `LLM · ${llm.provider}`,
        section: "services.llm",
        options: (llm.available || []).map((m) => ({
          name: m.name,
          size: m.size,
        })),
        current: llm.current,
        error: llm.error,
        fields: {
          primaryLabel: "Модель",
          primary: (value) => ({ model: value }),
          extra: [
            { key: "temperature", label: "Temperature",    value: config.services?.llm?.temperature, type: "number" },
            { key: "max_tokens",  label: "Max tokens",     value: config.services?.llm?.max_tokens,  type: "number" },
            { key: "num_ctx",     label: "Context window", value: config.services?.llm?.num_ctx,     type: "number" },
            { key: "keep_alive",  label: "Keep alive",     value: config.services?.llm?.keep_alive },
          ],
        },
      }));

      // ---- ASR ----------------------------------------------------------
      const asrProviderSelect = [
        { value: "whisper", name: "whisper (faster-whisper)" },
        { value: "riva",    name: "riva (NVIDIA Streaming)" },
      ];
      const asrCurrentProvider = config.services?.asr?.provider || asr.provider;
      grid.appendChild(modelCard({
        title: "ASR · провайдер",
        section: "services.asr",
        options: asrProviderSelect,
        current: asrCurrentProvider,
        fields: {
          primaryLabel: "Провайдер",
          primary: (value) => ({ provider: value }),
          extra: [
            { key: "wake_word_required", label: "wake_word_required (true/false)",
              value: String(!!config.services?.asr?.wake_word_required) },
            { key: "wake_words",         label: "wake_words (через запятую)",
              value: (() => { const w = config.services?.asr?.wake_words; return Array.isArray(w) ? w.join(", ") : (w || ""); })() },
          ],
        },
      }));

      // ---- ASR · whisper size ------------------------------------------
      grid.appendChild(modelCard({
        title: "ASR · Whisper size",
        section: "services.asr",
        options: (asr.whisper?.available || []).map((m) => ({ name: m.name })),
        current: asr.whisper?.current,
        fields: {
          primaryLabel: "Размер модели",
          primary: (value) => ({ model: value }),
        },
      }));

      // ---- TTS ----------------------------------------------------------
      grid.appendChild(modelCard({
        title: `TTS · ${tts.provider}`,
        section: "services.tts",
        options: (tts.available || []).map((m) => ({ name: m.name })),
        current: tts.current,
        fields: {
          primaryLabel: "Голос (speaker)",
          primary: (value) => ({ speaker: value }),
        },
      }));

      // ---- VLM ----------------------------------------------------------
      grid.appendChild(modelCard({
        title: "VLM",
        section: "services.vlm",
        options: (vlm.available || []).map((m) => ({ name: m.name })),
        current: vlm.current,
        error: vlm.error,
        fields: {
          primaryLabel: "Модель",
          primary: (value) => ({ model: value }),
          extra: [
            { key: "base_url",       label: "Base URL",       value: config.services?.vlm?.base_url },
            { key: "max_new_tokens", label: "Max new tokens", value: config.services?.vlm?.max_new_tokens, type: "number" },
          ],
        },
      }));
    } catch (e) {
      grid.innerHTML = "";
      grid.appendChild(el("div", { class: "card" }, el("div", { class: "card-body bad" }, `Ошибка: ${e.message}`)));
    }
  }

  render();
  return () => {};
}

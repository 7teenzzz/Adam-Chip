// Панель «Промты» — последние turn'ы с тем, что система подтянула в prompt.
// Полный system_prompt доступен только при включённом tuning.diagnostics.trace_prompts.

import { api } from "../api.js";

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

function fmtTime(iso) {
  if (!iso) return "—";
  return iso.slice(11, 19);
}

function badge(label, color = "muted") {
  return el("span", {
    class: "badge",
    style: `background:var(--${color}-bg, transparent); color:var(--${color}, var(--muted)); border:1px solid var(--${color}, var(--muted)); padding:2px 6px; margin-right:4px; font-size:11px; border-radius:3px`,
  }, label);
}

function inlineList(items) {
  if (!items || !items.length) return null;
  return el("div", { style: "color:var(--muted); font-size:12px; margin-top:4px; font-family:var(--font-mono)" }, items.join(" · "));
}

function injectionsBadges(item) {
  const out = [];
  if (item.visitor_name) out.push(badge(`name:${item.visitor_name}`, "accent"));
  if (item.semantic_used) out.push(badge(`semantic:${item.semantic_chars}ch`, "accent"));
  if ((item.recent_episodic || []).length) out.push(badge(`recent:${item.recent_episodic.length}`, "accent"));
  if (item.echo) {
    const e = item.echo;
    out.push(badge(`${e.pool}:${e.id}`, e.pool === "chinese" ? "warning" : "accent"));
  }
  if (item.mood && item.mood !== "neutral") out.push(badge(`mood:${item.mood}`, "warning"));
  out.push(badge(`turns:${item.history_turns_used || 0}`, "muted"));
  out.push(badge(`${item.prompt_chars || 0}ch`, "muted"));
  return out;
}

function turnRow(item, onShow) {
  const time = fmtTime(item.ts);
  const llmMs = item.timings?.llm_ms;
  const detailsBox = el("div");
  const detailsBtn = el("button", {
    class: "btn btn-ghost",
    style: "font-size:11px; padding:2px 8px",
    onclick: () => onShow(item, detailsBox, detailsBtn),
  }, item.system_prompt_available ? "PROMPT" : "DETAILS");
  return el("div", { class: "card", style: "margin-bottom:8px" }, [
    el("div", {
      class: "card-header",
      style: "display:flex; align-items:center; gap:8px; flex-wrap:wrap",
    }, [
      el("span", { class: "mono dim", style: "min-width:64px" }, time),
      el("span", { class: "mono", style: "color:var(--muted); min-width:64px" }, item.source || "—"),
      el("span", { style: "flex:1; color:var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap" }, item.transcript || ""),
      el("span", { class: "mono", style: "color:var(--accent); min-width:80px; text-align:right" },
        llmMs != null ? `${Math.round(llmMs)}мс` : "—"),
      detailsBtn,
    ]),
    el("div", { class: "card-body", style: "display:flex; flex-direction:column; gap:8px" }, [
      item.transcript ? el("div", { style: "color:var(--muted); font-size:12px" }, item.transcript) : null,
      item.reply ? el("div", {
        style: "color:var(--accent); font-size:13px; white-space:pre-wrap",
      }, "→ " + item.reply) : null,
      el("div", { style: "display:flex; flex-wrap:wrap; gap:4px; align-items:center" }, injectionsBadges(item)),
      inlineList(item.recent_episodic),
      item.llm_error ? el("div", {
        style: "color:var(--bad); font-family:var(--font-mono); font-size:12px",
      }, "Ошибка: " + item.llm_error) : null,
    ]),
    detailsBox,
  ]);
}

function buildDetailContent(item, fullData) {
  return el("div", { style: "padding:8px 0" }, [
    el("div", { class: "mono dim", style: "font-size:11px; margin-bottom:8px; padding:0 16px" },
      `ts=${item.ts}  source=${item.source}  prompt=${item.prompt_chars}ch  echo=${item.echo ? item.echo.pool + ":" + item.echo.id : "—"}`,
    ),
    el("div", { class: "mono", style: "white-space:pre-wrap; font-size:12px; max-height:60vh; overflow:auto; background:var(--bg-elev, #111); padding:12px; margin:0 0 8px; border-radius:4px; border:1px solid var(--border, #333)" },
      fullData?.system_prompt || "[system_prompt not captured — enable tuning.diagnostics.trace_prompts]",
    ),
    el("div", { style: "color:var(--muted); font-size:12px; padding:0 2px" },
      `transcript: ${item.transcript || ""}`),
    el("div", { style: "margin-top:4px; color:var(--accent); font-size:12px; padding:0 2px" },
      `reply: ${item.reply || ""}`),
  ]);
}

export function mount(target) {
  const status = el("div", { class: "muted", style: "font-size:12px; margin-bottom:8px" }, "загрузка…");
  const refreshBtn = el("button", { class: "btn", onclick: () => refresh() }, "Обновить");
  const limitInput = el("input", {
    type: "number", min: "1", max: "50", value: "20",
    class: "input mono", style: "width:64px",
  });
  const fullToggle = el("input", { type: "checkbox", id: "full-toggle" });
  const fullLabel = el("label", { for: "full-toggle", class: "muted", style: "font-size:12px; user-select:none" }, " грузить полные промты в списке (только метаданные хранятся всегда)");

  const list = el("div", { id: "prompts-list" });

  const header = el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Prompt Trace · последние turn'ы"),
      ]),
      el("div", { class: "card-body", style: "display:flex; gap:12px; align-items:center; flex-wrap:wrap" }, [
        refreshBtn,
        el("span", { class: "muted" }, "limit"),
        limitInput,
        el("span", { style: "display:flex; align-items:center; gap:4px" }, [fullToggle, fullLabel]),
        status,
      ]),
    ]),
    list,
  ]);
  target.appendChild(header);

  async function showFull(item, detailsBox, btn) {
    // Toggle: collapse if already open.
    if (detailsBox.children.length > 0) {
      detailsBox.innerHTML = "";
      if (btn) btn.textContent = item.system_prompt_available ? "PROMPT" : "DETAILS";
      return;
    }
    if (btn) btn.textContent = "…";
    let fullData = item;
    if (!item.system_prompt) {
      try {
        const data = await api.get(`/api/agent/prompts?limit=${Number(limitInput.value) || 20}&full=true`);
        const found = (data.items || []).find((x) => x.ts === item.ts);
        fullData = found || item;
        if (!data.trace_prompts_enabled) {
          fullData = { ...fullData, system_prompt: null };
        }
      } catch (e) {
        status.textContent = "ошибка: " + e.message;
      }
    }
    detailsBox.innerHTML = "";
    detailsBox.appendChild(buildDetailContent(item, fullData));
    if (btn) btn.textContent = "▲ СВЕРНУТЬ";
    detailsBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function refresh() {
    const limit = Math.max(1, Math.min(50, Number(limitInput.value) || 20));
    const full = fullToggle.checked;
    status.textContent = "загрузка…";
    try {
      const data = await api.get(`/api/agent/prompts?limit=${limit}&full=${full}`);
      const items = (data.items || []).slice().reverse();
      list.innerHTML = "";
      if (!items.length) {
        list.appendChild(el("div", { class: "card" }, el("div", { class: "card-body muted" }, "пока нет turn'ов")));
      } else {
        items.forEach((it) => list.appendChild(turnRow(it, showFull)));
      }
      status.innerHTML = `последних: <b>${items.length}</b>; trace_prompts: <b>${data.trace_prompts_enabled ? "ON" : "OFF (включи в Tuning → diagnostics)"}</b>`;
    } catch (e) {
      status.textContent = "ошибка: " + e.message;
    }
  }

  refresh();
  const timer = setInterval(refresh, 30000);
  return () => clearInterval(timer);
}

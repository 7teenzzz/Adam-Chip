import { api } from "../api.js";
import { state } from "../state.js";

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

function fmtMs(value) {
  if (value == null) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(2)}с`;
  return `${Math.round(value)}мс`;
}

function summaryCard(metric, label) {
  if (!metric) {
    return el("div", { class: "card" }, [
      el("div", { class: "card-header" }, el("span", { class: "card-title" }, label)),
      el("div", { class: "card-body muted" }, "нет данных"),
    ]);
  }
  return el("div", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, label),
      el("span", { class: "badge" }, `n=${metric.n}`),
    ]),
    el("div", { class: "card-body", style: "display:grid; grid-template-columns:repeat(4,1fr); gap:8px; font-family:var(--font-mono); font-size:13px" }, [
      kv("min", metric.min),
      kv("avg", metric.avg),
      kv("p95", metric.p95),
      kv("max", metric.max),
    ]),
  ]);
}

function kv(label, value) {
  return el("div", { style: "display:flex; flex-direction:column; gap:2px" }, [
    el("span", { class: "caps", style: "color:var(--muted); font-size:10px" }, label),
    el("span", { style: "color:var(--accent)" }, fmtMs(value)),
  ]);
}

function turnRow(t) {
  const ts = (t.ts || "").slice(11, 19);
  return el("tr", { class: "fade-in" }, [
    el("td", { class: "mono dim", style: "padding:6px 8px; white-space:nowrap" }, ts),
    el("td", { class: "mono", style: "padding:6px 8px; color:var(--muted)" }, t.source || "—"),
    el("td", { style: "padding:6px 8px; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" }, t.transcript || ""),
    el("td", { style: "padding:6px 8px; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--accent)" }, t.reply || ""),
    el("td", { class: "mono", style: "padding:6px 8px; text-align:right" }, fmtMs(t.asr_ms)),
    el("td", { class: "mono dim", style: "padding:6px 8px; text-align:right" }, fmtMs(t.vlm_ms)),
    el("td", { class: "mono", style: "padding:6px 8px; text-align:right" }, fmtMs(t.llm_ms)),
    el("td", { class: "mono", style: "padding:6px 8px; text-align:right" }, fmtMs(t.tts_ms)),
    el("td", { class: "mono", style: "padding:6px 8px; text-align:right; color:var(--accent)" }, fmtMs(t.total_ms)),
    el("td", { class: "mono dim", style: "padding:6px 8px; text-align:right" }, String(t.tts_chunks ?? "—")),
    el("td", { class: "mono dim", style: "padding:6px 8px; text-align:right" }, t.prompt_chars ? String(t.prompt_chars) : "—"),
  ]);
}

// ── Промты (inline) ────────────────────────────────────────────────────

function badge(label, color = "muted") {
  return el("span", {
    class: "badge",
    style: `background:transparent; color:var(--${color}, var(--muted)); border:1px solid var(--${color}, var(--muted)); padding:2px 6px; margin-right:4px; font-size:11px; border-radius:3px`,
  }, label);
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

function promptTurnRow(item, onShow) {
  const time = (item.ts || "").slice(11, 19);
  const llmMs = item.timings?.llm_ms;
  // Inline details container — expands below this card when Details is clicked.
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
      item.reply ? el("div", { style: "color:var(--accent); font-size:13px; white-space:pre-wrap" }, "→ " + item.reply) : null,
      el("div", { style: "display:flex; flex-wrap:wrap; gap:4px; align-items:center" }, injectionsBadges(item)),
      item.llm_error ? el("div", { style: "color:var(--bad); font-family:var(--font-mono); font-size:12px" }, "Ошибка: " + item.llm_error) : null,
    ]),
    detailsBox,
  ]);
}

function buildDetailContent(item, fullData) {
  return el("div", { style: "padding:8px 0" }, [
    el("div", { class: "mono dim", style: "font-size:11px; margin-bottom:8px; padding:0 16px" },
      `ts=${item.ts}  source=${item.source}  prompt=${item.prompt_chars}ch  echo=${item.echo ? item.echo.pool + ":" + item.echo.id : "—"}`),
    el("div", { class: "mono", style: "white-space:pre-wrap; font-size:12px; max-height:60vh; overflow:auto; background:var(--bg-elev, #111); padding:12px; margin:0 0 8px; border-radius:4px; border:1px solid var(--border, #333)" },
      fullData?.system_prompt || "[system_prompt не захвачен — включи tuning.diagnostics.trace_prompts]"),
    el("div", { style: "color:var(--muted); font-size:12px; padding:0 2px" }, `transcript: ${item.transcript || ""}`),
    el("div", { style: "margin-top:4px; color:var(--accent); font-size:12px; padding:0 2px" }, `reply: ${item.reply || ""}`),
  ]);
}

// ── Analytics helpers ─────────────────────────────────────────────────

function statusColor(status) {
  if (status === "ok") return "var(--good, #4caf50)";
  if (status === "warn") return "var(--warning, #ff9800)";
  if (status === "no_data" || status === "no_test_data") return "var(--muted)";
  if (status === "insufficient_data" || status === "degraded") return "var(--warning, #ff9800)";
  return "var(--muted)";
}

function automationBadge(level) {
  const map = {
    full: { label: "авто", color: "var(--good, #4caf50)" },
    proxy: { label: "прокси", color: "var(--accent)" },
    heuristic: { label: "эвристика", color: "var(--accent)" },
    partial: { label: "частично", color: "var(--warning, #ff9800)" },
    semi: { label: "тест", color: "var(--warning, #ff9800)" },
  };
  const cfg = map[level] || { label: level || "?", color: "var(--muted)" };
  return el("span", {
    style: `font-size:10px; padding:1px 5px; border-radius:2px; border:1px solid ${cfg.color}; color:${cfg.color}; letter-spacing:0.05em`,
  }, cfg.label);
}

function pct(val) {
  if (val == null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

function fmtVal(m) {
  if (m == null || m.value == null) return "—";
  if (m.value_pct != null) return `${m.value_pct}%`;
  if (typeof m.value === "number") return String(m.value);
  return String(m.value);
}

function metricCard(id, label, m) {
  if (!m) return el("div", { class: "card" }, el("div", { class: "card-body muted" }, label + ": нет данных"));
  const color = statusColor(m.status);
  const val = fmtVal(m);
  return el("div", { class: "card", style: "min-width:0" }, [
    el("div", { class: "card-header", style: "gap:6px" }, [
      el("span", { class: "mono", style: "font-size:11px; color:var(--muted)" }, id),
      el("span", { class: "card-title", style: "font-size:12px; flex:1" }, label),
      m.automation ? automationBadge(m.automation) : null,
    ]),
    el("div", { class: "card-body", style: "display:flex; flex-direction:column; gap:6px" }, [
      el("div", { style: `font-size:24px; font-family:var(--font-mono); color:${color}; line-height:1` }, val),
      m.note ? el("div", { style: "font-size:11px; color:var(--muted); line-height:1.4" }, m.note) : null,
      m.action_kinds ? el("div", { style: "font-size:11px; font-family:var(--font-mono); color:var(--muted)" },
        Object.entries(m.action_kinds).map(([k, v]) => `${k}:${v}`).join("  ")) : null,
      m.avg != null && id === "M9" ? el("div", { style: "font-size:11px; color:var(--muted); font-family:var(--font-mono)" },
        `avg:${m.avg} med:${m.median} max:${m.max}`) : null,
    ]),
  ]);
}

function latencyBlock(m10) {
  if (!m10 || m10.status === "no_data") return el("div", { class: "card-body muted" }, "нет данных о латентности");
  const rows = [
    ["ASR", m10.asr_ms],
    ["LLM", m10.llm_ms],
    ["TTS", m10.tts_ms],
    ["∑ Total", m10.total_ms],
  ];
  return el("div", { style: "display:grid; grid-template-columns:repeat(4,1fr); gap:8px" },
    rows.map(([label, s]) => el("div", { class: "card", style: "min-width:0" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, label),
        automationBadge("full"),
      ]),
      s ? el("div", { class: "card-body", style: "display:grid; grid-template-columns:repeat(4,1fr); gap:4px; font-family:var(--font-mono); font-size:12px" }, [
        kv("min", s.min), kv("avg", s.avg), kv("p95", s.p95), kv("max", s.max),
      ]) : el("div", { class: "card-body muted" }, "—"),
    ]))
  );
}

function blockSection(title, cards) {
  return el("section", { class: "col", style: "gap:8px" }, [
    el("div", { class: "caps", style: "color:var(--muted); font-size:11px; padding:4px 0; border-bottom:1px solid var(--line)" }, title),
    el("div", { style: "display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:8px" }, cards),
  ]);
}

function sessionsTable(sessions) {
  if (!sessions || !sessions.length) return el("div", { class: "card-body muted" }, "нет закрытых сессий");
  const rows = sessions.slice().reverse().slice(0, 20);
  return el("div", { style: "overflow-x:auto" }, [
    el("table", { style: "width:100%; border-collapse:collapse; font-size:12px" }, [
      el("thead", null, el("tr", { style: "background:var(--bg-2); color:var(--muted); font-size:10px; text-transform:uppercase" }, [
        ["Время", "left"], ["Turn'ы", "right"], ["Сек", "right"], ["Имя", "left"],
        ["Значимость", "right"], ["Темы", "left"], ["Эпизод", "center"],
      ].map(([h, a]) => el("th", { style: `padding:6px 8px; text-align:${a}` }, h)))),
      el("tbody", null, rows.map(s => el("tr", { style: "border-bottom:1px solid var(--bg-3)" }, [
        el("td", { style: "padding:5px 8px; font-family:var(--font-mono); color:var(--muted)" }, (s.ts || "").slice(0, 16)),
        el("td", { style: "padding:5px 8px; text-align:right; font-family:var(--font-mono)" }, String(s.turn_count ?? "—")),
        el("td", { style: "padding:5px 8px; text-align:right; font-family:var(--font-mono)" }, String(s.duration_s ?? "—")),
        el("td", { style: "padding:5px 8px" }, s.visitor_name || el("span", { class: "muted" }, "анон")),
        el("td", { style: "padding:5px 8px; text-align:right; font-family:var(--font-mono); color:var(--accent)" }, s.salience != null ? s.salience.toFixed(3) : "—"),
        el("td", { style: "padding:5px 8px; color:var(--muted)" }, (s.themes || []).slice(0, 3).join(", ") || "—"),
        el("td", { style: "padding:5px 8px; text-align:center" }, s.episode_committed
          ? el("span", { style: "color:var(--good, #4caf50)" }, "✓")
          : el("span", { class: "muted" }, "—")),
      ]))),
    ]),
  ]);
}

// ── Mount ─────────────────────────────────────────────────────────────

export function mount(target) {
  // ── Tab state ──
  let activeTab = "metrics";

  const metricsBtn  = el("button", { class: "btn",        onclick: () => switchTab("metrics")   }, "Метрики");
  const analyticsBtn = el("button", { class: "btn btn-ghost", onclick: () => switchTab("analytics") }, "Аналитика");
  const promptsBtn  = el("button", { class: "btn btn-ghost", onclick: () => switchTab("prompts")  }, "Промты");

  const metricsSection   = el("div");
  const analyticsSection = el("div", { style: "display:none" });
  const promptsSection   = el("div", { style: "display:none" });

  function switchTab(tab) {
    activeTab = tab;
    metricsSection.style.display   = tab === "metrics"   ? "" : "none";
    analyticsSection.style.display = tab === "analytics" ? "" : "none";
    promptsSection.style.display   = tab === "prompts"   ? "" : "none";
    metricsBtn.className   = tab === "metrics"   ? "btn" : "btn btn-ghost";
    analyticsBtn.className = tab === "analytics" ? "btn" : "btn btn-ghost";
    promptsBtn.className   = tab === "prompts"   ? "btn" : "btn btn-ghost";
    if (tab === "analytics" && !_dashboardLoaded) refreshDashboard();
  }

  // ── Analytics section ──
  let _dashboardLoaded = false;
  const dashRoot = el("div", { class: "col", style: "gap:12px" });
  const dashStatus = el("div", { class: "muted", style: "font-size:12px" }, "");
  const dashRefreshBtn = el("button", { class: "btn", onclick: () => refreshDashboard() }, "Обновить");
  const sessionsRoot = el("div");

  analyticsSection.appendChild(el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "row" }, [
      el("div", { class: "caps" }, "Дипломные метрики · автовычисление"),
      el("span", { class: "spacer" }),
      dashStatus,
      dashRefreshBtn,
    ]),
    dashRoot,
    el("section", { class: "card" }, [
      el("div", { class: "card-header" }, el("span", { class: "card-title" }, "История сессий")),
      el("div", { class: "card-body", style: "padding:0" }, [sessionsRoot]),
    ]),
  ]));

  async function refreshDashboard() {
    dashStatus.textContent = "вычисление…";
    _dashboardLoaded = true;
    try {
      const [dash, sess] = await Promise.all([
        api.get("/api/metrics/dashboard?window=300"),
        api.get("/api/metrics/sessions?limit=50"),
      ]);

      dashRoot.innerHTML = "";
      const b = dash.blocks || {};
      const rn = b.role_normativity || {};
      const mt = b.memory_temporal || {};
      const ia = b.interactivity || {};

      dashRoot.appendChild(blockSection("3.4.2 Удержание роли и нормативность", [
        metricCard("M1", "Стабильность персонажа", rn.m1_persona_consistency),
        metricCard("M2", "Инжекция echo-реплик", rn.m2_echo_injection),
        metricCard("M3", "Отклонения ActionLayer", rn.m3_action_rejection),
        metricCard("M4", "Дрейф стиля (cosine)", rn.m4_style_drift),
      ]));

      dashRoot.appendChild(blockSection("3.4.3 Память и темпоральная связность", [
        metricCard("M5", "Retrieval-активация", mt.m5_retrieval_proxy),
        metricCard("M6", "Salience — внутр. согласованность", mt.m6_salience_internal),
        metricCard("M7", "Консолидация — охват", mt.m7_consolidation),
        metricCard("M8", "Межсессионная память", mt.m8_cross_session_proxy),
      ]));

      dashRoot.appendChild(blockSection("3.4.4 Интеракционность и инициатива", [
        metricCard("M9", "Длина диалога (avg turn'ов)", ia.m9_dialog_length),
        metricCard("M11", "Wake word (OWW scores)", ia.m11_wake_word),
        metricCard("M12", "Half-duplex нарушения", ia.m12_half_duplex),
        metricCard("M13", "Смены вовлечённости", ia.m13_engagement),
      ]));

      // M10 latency — отдельный широкий блок
      dashRoot.appendChild(el("section", { class: "col", style: "gap:8px" }, [
        el("div", { class: "caps", style: "color:var(--muted); font-size:11px; padding:4px 0; border-bottom:1px solid var(--line)" },
          "M10 — Латентность ответа"),
        latencyBlock(ia.m10_latency),
      ]));

      sessionsRoot.innerHTML = "";
      sessionsRoot.appendChild(sessionsTable(sess.sessions || []));

      const ts = (dash.computed_at || "").slice(11, 19);
      dashStatus.textContent = `обновлено ${ts} · окно: ${dash.window_turns} turn'ов · ${dash.window_sessions} сессий`;
    } catch (e) {
      dashStatus.textContent = "ошибка: " + e.message;
    }
  }

  // ── Metrics section ──
  const summaryRoot = el("div", { class: "grid-4", id: "metrics-summary", style: "gap:12px" });
  const tableBody = el("tbody", { id: "metrics-tbody" });
  const refreshBtn = el("button", { class: "btn", onclick: () => refresh() }, "Обновить");
  const exportBtn = el("a", {
    class: "btn btn-ghost",
    href: "/api/metrics/export",
    target: "_blank",
    rel: "noopener",
  }, "Скачать JSONL");

  const eventLogBody = el("div", {
    id: "metrics-events",
    style: "max-height:36vh; overflow-y:auto; font-family:var(--font-mono); font-size:11px",
  });
  const eventClearBtn = el("button", { class: "btn btn-ghost", onclick: () => { eventLogBody.innerHTML = ""; } }, "Очистить");
  const eventFilter = el("input", {
    class: "input mono",
    type: "text",
    placeholder: "фильтр по типу (напр. adam_reply)",
    style: "flex:1; font-size:11px",
  });

  metricsSection.appendChild(el("section", { class: "col" }, [
    el("div", { class: "row" }, [
      el("div", { class: "caps" }, "Сводка по последним 50 репликам · таблица: 17 последних"),
      el("span", { class: "spacer" }),
      refreshBtn,
      exportBtn,
    ]),
    summaryRoot,
    el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "История инференса"),
        el("span", { class: "caps", id: "metrics-meta" }, ""),
      ]),
      el("div", { class: "card-body", style: "padding:0; overflow-x:auto" }, [
        el("table", { style: "width:100%; border-collapse:collapse; font-size:13px" }, [
          el("thead", null, el("tr", { style: "background:var(--bg-2); color:var(--muted); text-transform:uppercase; font-size:10px; letter-spacing:0.08em" }, [
            el("th", { style: "padding:8px; text-align:left" }, "Время"),
            el("th", { style: "padding:8px; text-align:left" }, "Источник"),
            el("th", { style: "padding:8px; text-align:left" }, "Зритель"),
            el("th", { style: "padding:8px; text-align:left" }, "Адам"),
            el("th", { style: "padding:8px; text-align:right" }, "ASR"),
            el("th", { style: "padding:8px; text-align:right; opacity:0.6" }, "VLM"),
            el("th", { style: "padding:8px; text-align:right" }, "LLM"),
            el("th", { style: "padding:8px; text-align:right" }, "TTS"),
            el("th", { style: "padding:8px; text-align:right" }, "∑"),
            el("th", { style: "padding:8px; text-align:right" }, "Чанки"),
            el("th", { style: "padding:8px; text-align:right; opacity:0.6" }, "Sys.ch"),
          ])),
          tableBody,
        ]),
      ]),
    ]),
    el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Журнал событий (SSE)"),
        el("span", { class: "spacer" }),
        eventFilter,
        eventClearBtn,
      ]),
      el("div", { class: "card-body", style: "padding:4px 8px" }, [eventLogBody]),
    ]),
  ]));

  // ── Prompts section ──
  const promptStatus = el("div", { class: "muted", style: "font-size:12px; margin-bottom:8px" }, "загрузка…");
  const promptRefreshBtn = el("button", { class: "btn", onclick: () => refreshPrompts() }, "Обновить");
  const limitInput = el("input", {
    type: "number", min: "1", max: "50", value: "20",
    class: "input mono", style: "width:64px",
  });
  const fullToggle = el("input", { type: "checkbox", id: "full-toggle-m" });
  const promptList = el("div");

  promptsSection.appendChild(el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "card" }, [
      el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Prompt Trace · последние turn'ы")),
      el("div", { class: "card-body", style: "display:flex; gap:12px; align-items:center; flex-wrap:wrap" }, [
        promptRefreshBtn,
        el("span", { class: "muted" }, "limit"),
        limitInput,
        el("span", { style: "display:flex; align-items:center; gap:4px" }, [
          fullToggle,
          el("label", { for: "full-toggle-m", class: "muted", style: "font-size:12px; user-select:none" }, " грузить полные промты"),
        ]),
        promptStatus,
      ]),
    ]),
    promptList,
  ]));

  target.appendChild(el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "row", style: "gap:8px; padding-bottom:4px; border-bottom:1px solid var(--line)" }, [
      metricsBtn,
      analyticsBtn,
      promptsBtn,
    ]),
    metricsSection,
    analyticsSection,
    promptsSection,
  ]));

  // ── Metrics refresh ──
  async function refresh() {
    try {
      const [summary, list] = await Promise.all([
        api.get("/api/metrics/summary?window=50"),
        api.get("/api/metrics/turns?limit=17"),
      ]);
      summaryRoot.innerHTML = "";
      const m = summary.metrics || {};
      summaryRoot.appendChild(summaryCard(m.asr_ms, "ASR"));
      summaryRoot.appendChild(summaryCard(m.llm_ms, "LLM"));
      summaryRoot.appendChild(summaryCard(m.tts_ms, "TTS"));
      summaryRoot.appendChild(summaryCard(m.total_ms, "∑ Total"));

      tableBody.innerHTML = "";
      const turns = (list.turns || []).slice().reverse();
      turns.forEach((t) => tableBody.appendChild(turnRow(t)));
      const meta = document.getElementById("metrics-meta");
      if (meta) meta.textContent = `показано ${turns.length} · окно сводки ${summary.count} · файл append-only в data/adam/inference_metrics.jsonl`;
    } catch (e) {
      console.error("metrics refresh failed", e);
    }
  }

  // ── Prompts refresh ──
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
        if (!data.trace_prompts_enabled) fullData = { ...fullData, system_prompt: null };
      } catch (e) {
        promptStatus.textContent = "ошибка: " + e.message;
      }
    }
    detailsBox.innerHTML = "";
    detailsBox.appendChild(buildDetailContent(item, fullData));
    if (btn) btn.textContent = "▲ СВЕРНУТЬ";
    detailsBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function refreshPrompts() {
    const limit = Math.max(1, Math.min(50, Number(limitInput.value) || 20));
    const full = fullToggle.checked;
    promptStatus.textContent = "загрузка…";
    try {
      const data = await api.get(`/api/agent/prompts?limit=${limit}&full=${full}`);
      const items = (data.items || []).slice().reverse();
      promptList.innerHTML = "";
      if (!items.length) {
        promptList.appendChild(el("div", { class: "card" }, el("div", { class: "card-body muted" }, "пока нет turn'ов")));
      } else {
        items.forEach((it) => promptList.appendChild(promptTurnRow(it, showFull)));
      }
      promptStatus.innerHTML = `последних: <b>${items.length}</b>; trace_prompts: <b>${data.trace_prompts_enabled ? "ON" : "OFF (включи в Tuning → diagnostics)"}</b>`;
    } catch (e) {
      promptStatus.textContent = "ошибка: " + e.message;
    }
  }

  refresh();

  function appendEvent(ev) {
    const filter = eventFilter.value.trim().toLowerCase();
    if (filter && !ev.type?.toLowerCase().includes(filter)) return;
    const ts = (ev.ts || "").slice(11, 19);
    const payloadStr = (() => {
      const p = ev.payload;
      if (!p) return "";
      if (p.text) return String(p.text).slice(0, 120);
      if (p.error) return `! ${p.error}`;
      const keys = Object.keys(p).slice(0, 4);
      return keys.map((k) => `${k}=${typeof p[k] === "object" ? "{…}" : p[k]}`).join(" ");
    })();
    const line = el("div", {
      class: "fade-in",
      style: "display:grid; grid-template-columns:52px 130px 1fr; gap:8px; padding:3px 0; border-bottom:1px solid var(--bg-3); align-items:start",
    }, [
      el("span", { style: "color:var(--muted); opacity:0.7" }, ts),
      el("span", { style: "color:var(--accent)" }, ev.type || "?"),
      el("span", { style: "color:var(--muted); white-space:pre-wrap; word-break:break-word" }, payloadStr),
    ]);
    eventLogBody.prepend(line);
    while (eventLogBody.children.length > 200) eventLogBody.removeChild(eventLogBody.lastChild);
  }

  const unsubscribe = state.subscribe("last_events", (payload) => {
    const ev = payload.last;
    if (!ev) return;
    appendEvent(ev);
    if (ev.type === "adam_reply") refresh();
  });

  const metricsInterval = setInterval(refresh, 15000);
  const promptsInterval = setInterval(() => {
    if (activeTab === "prompts") refreshPrompts();
  }, 30000);

  return () => {
    unsubscribe();
    clearInterval(metricsInterval);
    clearInterval(promptsInterval);
  };
}

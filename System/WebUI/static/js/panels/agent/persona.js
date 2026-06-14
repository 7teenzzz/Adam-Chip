// Panel: Личность (#/agent/persona)
// Preset selector + AIIM matrix (12 aspects, 4×3 grid) + Identity.md section editors.
// D-04: Identity.md is NOT shown as a full textarea — only "Интенции" and "Голос" sections.
// API: GET /api/tuning, PUT /api/tuning, POST /api/tuning/preset/{name},
//      GET /api/persona, PUT /api/persona {path, content}

import { api } from "../../api.js";
import { toast } from "../../widgets/toast.js";

// ── DOM builder (local copy — do NOT import from elsewhere) ──────────────────

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

// ── Identity.md section parser ────────────────────────────────────────────────

/**
 * Extract a named "## Section" body from a markdown string.
 * Returns the trimmed content between the section header and the next "## " header.
 * Returns null if the section is not found.
 */
function extractSection(markdown, sectionName) {
  const lines = markdown.split("\n");
  const startIdx = lines.findIndex((l) => l.trim() === `## ${sectionName}`);
  if (startIdx === -1) return null;
  const endIdx = lines.findIndex((l, i) => i > startIdx && l.startsWith("## "));
  const sectionLines = endIdx === -1 ? lines.slice(startIdx + 1) : lines.slice(startIdx + 1, endIdx);
  return sectionLines.join("\n").trim();
}

/**
 * Reconstruct the full file with one section's body replaced.
 * The header line, before-section content, and after-section content are
 * preserved verbatim — including code fences in other sections (T-42-03).
 */
function reconstructFile(original, sectionName, newContent) {
  const lines = original.split("\n");
  const startIdx = lines.findIndex((l) => l.trim() === `## ${sectionName}`);
  if (startIdx === -1) return original; // section not found → return unchanged
  const endIdx = lines.findIndex((l, i) => i > startIdx && l.startsWith("## "));
  const before = lines.slice(0, startIdx);
  const after = endIdx === -1 ? [] : lines.slice(endIdx);
  return [...before, `## ${sectionName}`, "", ...newContent.split("\n"), "", ...after].join("\n");
}

// ── AIIM metadata ─────────────────────────────────────────────────────────────
// Copied verbatim from tuning.js (mirrored in Identity.md, iAdam.json).

const AIIM_ASPECTS = [
  { code: "wi", name: "воля",          plan: "P", level: 4, ac: "Ac", or: "Or", desc: "хочу, выбираю, направляю" },
  { code: "lo", name: "эмпатия",       plan: "S", level: 4, ac: "Ac", or: "Or", desc: "замечаю чужое состояние, хочу понять" },
  { code: "im", name: "идеи",          plan: "P", level: 3, ac: "Ac", or: "Ch", desc: "связываю несвязанное, шучу" },
  { code: "ho", name: "этика",         plan: "I", level: 3, ac: "Pa", or: "Or", desc: "держу границы" },
  { code: "co", name: "логика",        plan: "T", level: 4, ac: "Ac", or: "Or", desc: "анализирую, удерживаю дистанцию" },
  { code: "em", name: "эмоция",        plan: "B", level: 3, ac: "Ac", or: "Ch", desc: "окрашиваю восприятие, проявляюсь" },
  { code: "be", name: "действие",      plan: "S", level: 3, ac: "Ac", or: "Or", desc: "отвечаю, технофлора двигается" },
  { code: "sp", name: "смысл",         plan: "T", level: 4, ac: "Pa", or: "Or", desc: "вижу масштаб" },
  { code: "se", name: "самоосознание", plan: "I", level: 4, ac: "Ac", or: "Ch", desc: "наблюдаю за тем, чем становлюсь" },
  { code: "pe", name: "восприятие",    plan: "T", level: 3, ac: "Ac", or: "Or", desc: "чувствую через технофлору" },
  { code: "me", name: "память",        plan: "B", level: 2, ac: "Pa", or: "Ch", desc: "повреждена, восстанавливается обрывками" },
  { code: "at", name: "внимание",      plan: "S", level: 4, ac: "Ac", or: "Or", desc: "слушаю до конца, не игнорирую" },
];

// Inline colors (per UI-SPEC §4: no new CSS variables for plan colors — inline styles only)
const PLAN_META = {
  P: { label: "я сам",   color: "#a78bfa" },
  S: { label: "другие",  color: "#60a5fa" },
  I: { label: "связки",  color: "var(--accent)" },
  B: { label: "тело",    color: "#f97316" },
  T: { label: "трансц.", color: "var(--cyan)" },
};

const LEVEL_LABELS = ["", "зачаточный", "стабильный", "сложный", "мастерский"];

// ── Preset selector card ──────────────────────────────────────────────────────

/**
 * Build the preset selector card.
 * Badges for each personality preset; clicking applies via POST /api/tuning/preset/{name}.
 * onPresetApplied(tuningData) is called after a successful preset application.
 */
function makePresetCard(onPresetApplied) {
  const badgesRow = el("div", { style: "display:flex; flex-wrap:wrap; gap:8px" });
  const statusSpan = el("span", { class: "muted", style: "font-size:12px" }, "загрузка…");

  let activePreset = null;
  let allBadges = {};

  function renderBadges(presets, active) {
    activePreset = active;
    allBadges = {};
    badgesRow.innerHTML = "";
    const names = Object.keys(presets || {});
    if (names.length === 0) {
      badgesRow.appendChild(el("span", { class: "muted", style: "font-size:13px" }, "Пресеты не настроены"));
      statusSpan.textContent = "";
      return;
    }
    names.forEach((name) => {
      const preset = presets[name];
      const isActive = name === active;
      const badge = el("button", {
        class: "badge" + (isActive ? " ok" : ""),
        style: [
          "cursor:pointer; padding:4px 12px; border:none; font-size:13px; font-weight:500",
          isActive ? "border:1px solid var(--accent); color:var(--accent)" : "",
        ].join("; "),
        title: preset.description || name,
        onclick: async () => {
          if (name === activePreset) return;
          // Dim all badges during POST
          Object.values(allBadges).forEach((b) => { b.style.opacity = "0.5"; b.disabled = true; });
          statusSpan.textContent = "применяю…";
          try {
            await api.post(`/api/tuning/preset/${name}`, {});
            // Reload tuning to get updated weights
            const newTuning = await api.get("/api/tuning");
            activePreset = name;
            renderBadges(newTuning.personality_presets ?? {}, name);
            statusSpan.textContent = "применено ✓";
            setTimeout(() => { statusSpan.textContent = ""; }, 2500);
            if (onPresetApplied) onPresetApplied(newTuning);
          } catch (e) {
            Object.values(allBadges).forEach((b) => { b.style.opacity = ""; b.disabled = false; });
            toast(`Не удалось применить пресет: ${e.message}`, "bad", 5000);
            statusSpan.textContent = "";
          }
        },
      }, name);
      allBadges[name] = badge;
      badgesRow.appendChild(badge);
    });
    statusSpan.textContent = active ? `Активен: ${active}` : "";
  }

  const card = el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Пресет личности"),
      statusSpan,
    ]),
    el("div", { class: "card-body" }, [badgesRow]),
  ]);

  return { card, renderBadges };
}

// ── AIIM matrix card ──────────────────────────────────────────────────────────

/**
 * Build the 4×3 AIIM matrix card with weight (0-1) and level (0-4) sliders.
 * Returns { card, getValues() -> {base_weights, levels} }.
 */
function makeAiimMatrixCard(tuningData) {
  const weights = (tuningData.identity ?? {}).base_weights ?? {};
  const levels  = (tuningData.identity ?? {}).levels ?? {};

  const getters = []; // each entry: { code, getWeight, getLevel }

  const cells = AIIM_ASPECTS.map((asp) => {
    const initWeight = weights[asp.code] ?? 0.5;
    const initLevel  = levels[asp.code]  ?? asp.level;

    // ── Plan dot (right-aligned)
    const pm = PLAN_META[asp.plan] ?? PLAN_META.T;
    const planDot = el("span", {
      title: `план: ${pm.label}`,
      style: `color:${pm.color}; font-size:10px; margin-left:auto`,
    }, "●");

    // ── Header row: code + name + plan dot
    const header = el("div", {
      style: "display:flex; align-items:center; gap:0; margin-bottom:6px",
    }, [
      el("span", {
        style: "font-family:var(--font-mono); color:var(--dim); font-size:11px",
      }, asp.code),
      el("span", {
        style: "color:var(--text); font-size:13px; font-weight:500; margin-left:8px",
      }, asp.name),
      planDot,
    ]);

    // ── Weight row
    const weightDisplay = el("span", {
      style: "font-family:var(--font-mono); font-size:11px; color:var(--accent); min-width:36px; text-align:right",
    }, initWeight.toFixed(2));
    const weightSlider = el("input", {
      type: "range", min: "0", max: "1", step: "0.01",
      value: String(initWeight),
      style: "flex:1; accent-color:var(--accent); width:100%",
    });
    weightSlider.addEventListener("input", () => {
      weightDisplay.textContent = parseFloat(weightSlider.value).toFixed(2);
    });
    const weightRow = el("div", {
      style: "display:flex; align-items:center; gap:6px; margin-bottom:4px",
    }, [weightSlider, weightDisplay]);

    // ── Level row
    const levelLabel = LEVEL_LABELS[initLevel] ? `L${initLevel}` : "L0";
    const levelDisplay = el("span", {
      style: "font-size:11px; color:var(--muted); min-width:36px; text-align:right",
    }, levelLabel);
    const levelSlider = el("input", {
      type: "range", min: "0", max: "4", step: "1",
      value: String(initLevel),
      style: "flex:1; accent-color:var(--accent); width:100%",
    });
    levelSlider.addEventListener("input", () => {
      const v = parseInt(levelSlider.value, 10);
      levelDisplay.textContent = v > 0 ? `L${v}` : "L0";
    });
    const levelRow = el("div", {
      style: "display:flex; align-items:center; gap:6px",
    }, [levelSlider, levelDisplay]);

    getters.push({
      code: asp.code,
      getWeight: () => parseFloat(weightSlider.value),
      getLevel:  () => parseInt(levelSlider.value, 10),
    });

    return el("div", {
      style: "border:1px solid var(--line); border-radius:var(--radius-s); padding:8px 12px; background:var(--bg-2)",
    }, [header, weightRow, levelRow]);
  });

  // ── 4×3 grid
  const grid = el("div", { class: "grid-3" }, cells);

  // ── Save button
  const saveBtn = el("button", { class: "btn btn-primary" }, "Сохранить матрицу");
  saveBtn.addEventListener("click", async () => {
    const orig = saveBtn.textContent;
    saveBtn.textContent = "Сохраняется…";
    saveBtn.disabled = true;

    const base_weights = {};
    const levelMap = {};
    getters.forEach(({ code, getWeight, getLevel }) => {
      base_weights[code] = getWeight();
      levelMap[code] = getLevel();
    });

    try {
      // PUT /api/tuning with identity.base_weights (and levels if server supports it)
      await api.raw("/api/tuning", {
        method: "PUT",
        body: { identity: { base_weights, levels: levelMap } },
      });
      toast("Матрица сохранена", "ok");
    } catch (e) {
      toast(`Ошибка сохранения матрицы: ${e.message}`, "bad", 5000);
    } finally {
      saveBtn.textContent = orig;
      saveBtn.disabled = false;
    }
  });

  const card = el("section", { class: "card card-full" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Матрица AIIM · 12 аспектов"),
      el("span", { style: "font-size:11px; color:var(--dim)" }, "A-2 · Identity.md"),
    ]),
    el("div", { class: "card-body" }, [
      grid,
      el("div", { style: "margin-top:12px" }, [saveBtn]),
    ]),
  ]);

  function getValues() {
    const base_weights = {};
    const levelMap = {};
    getters.forEach(({ code, getWeight, getLevel }) => {
      base_weights[code] = getWeight();
      levelMap[code] = getLevel();
    });
    return { base_weights, levels: levelMap };
  }

  return { card, getValues };
}

// ── Identity.md block editor ──────────────────────────────────────────────────

/**
 * Build a single block editor card for one ## section of Identity.md.
 * sectionName: "Интенции" or "Голос"
 * getIdentityContent: () -> current full Identity.md string
 * setIdentityContent: (newFull) -> void (update local copy after save)
 */
function makeBlockEditor(sectionName, getIdentityContent, setIdentityContent) {
  let isEditing = false;

  const viewDiv = el("div", {
    class: "md-render",
    style: "font-size:14px; line-height:1.6; color:var(--text)",
  });

  const editTextarea = el("textarea", {
    class: "textarea field-wide",
    style: "min-height:120px; display:none; font-size:13px; font-family:var(--font-mono)",
  });

  function renderView() {
    const content = extractSection(getIdentityContent(), sectionName) ?? "";
    if (window.marked) {
      viewDiv.innerHTML = window.marked.parse(content);
    } else {
      viewDiv.innerHTML = "";
      viewDiv.appendChild(el("pre", { style: "white-space:pre-wrap; font-size:13px" }, content));
    }
  }

  renderView();

  const editBtn = el("button", { class: "btn" }, "Редактировать");
  const saveBtn = el("button", { class: "btn btn-primary", style: "display:none" }, "Сохранить");
  const cancelBtn = el("button", { class: "btn btn-ghost", style: "display:none" }, "Отмена");
  const statusSpan = el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });

  function enterEdit() {
    isEditing = true;
    const content = extractSection(getIdentityContent(), sectionName) ?? "";
    editTextarea.value = content;
    viewDiv.style.display = "none";
    editTextarea.style.display = "";
    editBtn.style.display = "none";
    saveBtn.style.display = "";
    cancelBtn.style.display = "";
  }

  function exitEdit() {
    isEditing = false;
    editTextarea.style.display = "none";
    viewDiv.style.display = "";
    editBtn.style.display = "";
    saveBtn.style.display = "none";
    cancelBtn.style.display = "none";
    statusSpan.textContent = "";
    statusSpan.className = "badge";
  }

  editBtn.addEventListener("click", enterEdit);
  cancelBtn.addEventListener("click", exitEdit);

  saveBtn.addEventListener("click", async () => {
    const reconstructed = reconstructFile(getIdentityContent(), sectionName, editTextarea.value);
    statusSpan.className = "badge warn";
    statusSpan.textContent = "сохранение…";
    saveBtn.disabled = true;

    try {
      await api.raw("/api/persona", {
        method: "PUT",
        body: { path: "Agent-Adam-Chip/About/Identity.md", content: reconstructed },
      });
      setIdentityContent(reconstructed);
      renderView();
      exitEdit();
      statusSpan.className = "badge ok";
      statusSpan.textContent = "сохранено";
      setTimeout(() => { statusSpan.textContent = ""; statusSpan.className = "badge"; }, 2500);
      toast(`${sectionName}: сохранено`, "ok");
    } catch (e) {
      statusSpan.className = "badge bad";
      statusSpan.textContent = "ошибка";
      toast(`Ошибка сохранения ${sectionName}: ${e.message}`, "bad", 5000);
    } finally {
      saveBtn.disabled = false;
    }
  });

  const card = el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, sectionName),
      el("span", { class: "spacer" }),
      statusSpan,
      editBtn,
      saveBtn,
      cancelBtn,
    ]),
    el("div", { class: "card-body" }, [viewDiv, editTextarea]),
  ]);

  return { card };
}

// ── mount() — panel entry point ───────────────────────────────────────────────

export function mount(target) {
  const disposables = [];

  // Loading indicator
  const loadingMsg = el("div", { class: "muted", style: "font-size:12px; padding:8px 0" }, "загрузка…");
  const container = el("div", { class: "col", style: "gap:12px" });

  target.appendChild(el("section", { class: "col", style: "gap:12px" }, [loadingMsg, container]));

  // Shared state: local copy of full Identity.md content for block editors
  let identityContent = "";
  const getIdentityContent = () => identityContent;
  const setIdentityContent = (v) => { identityContent = v; };

  // Mutable reference to AIIM matrix card (re-rendered on preset apply)
  let matrixCard = null;

  // Preset card (persists across re-renders)
  const presetCtl = makePresetCard((newTuning) => {
    // Re-render AIIM matrix with updated weights after preset apply
    if (matrixCard) {
      const oldCard = matrixCard;
      const { card, getValues } = makeAiimMatrixCard(newTuning);
      matrixCard = card;
      oldCard.replaceWith(card);
    }
  });

  async function renderAll() {
    loadingMsg.textContent = "загрузка…";
    container.innerHTML = "";

    try {
      const [tuning, persona] = await Promise.all([
        api.get("/api/tuning"),
        api.get("/api/persona"),
      ]);

      // Find Identity.md in persona files
      const identityFile = (persona.files || []).find(
        (f) => f.path && f.path.includes("Identity.md")
      );
      identityContent = identityFile ? (identityFile.content || "") : "";

      // ── Preset card
      const presets = tuning.personality_presets ?? {};
      const active  = tuning.active_preset ?? null;
      presetCtl.renderBadges(presets, active);
      container.appendChild(presetCtl.card);

      // ── AIIM matrix card
      const { card: mCard } = makeAiimMatrixCard(tuning);
      matrixCard = mCard;
      container.appendChild(matrixCard);

      // ── Block editors: Интенции and Голос
      const intentionsEditor = makeBlockEditor("Интенции", getIdentityContent, setIdentityContent);
      const voiceEditor      = makeBlockEditor("Голос",    getIdentityContent, setIdentityContent);
      container.appendChild(intentionsEditor.card);
      container.appendChild(voiceEditor.card);

      loadingMsg.textContent = "";
    } catch (e) {
      loadingMsg.className = "bad";
      loadingMsg.textContent = `Ошибка загрузки: ${e.message}`;
    }
  }

  renderAll();

  return function teardown() {
    while (disposables.length) {
      const fn = disposables.pop();
      try { fn(); } catch (_) {}
    }
  };
}

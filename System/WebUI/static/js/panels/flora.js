import { api } from "../api.js";
import { toast } from "../widgets/toast.js";

// ── DOM helper (mirrored from settings.js) ────────────────────────────────────
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

// ── Slider with live numeric label ───────────────────────────────────────────
// Returns { root, getValue } so callers can read the current value.
function makeSlider({ label, hint, min, max, step, initValue, decimals = 0 }) {
  const numDecimals = decimals ?? (step < 1 ? 2 : 0);
  const fmt = (v) => Number(v).toFixed(numDecimals);

  const valueLabel = el("span", {
    class: "mono",
    style: "min-width:42px; text-align:right; color:var(--accent); font-size:12px; font-weight:600",
  }, fmt(initValue ?? min));

  const slider = el("input", {
    type: "range",
    class: "input",
    style: "flex:1; min-width:120px; cursor:pointer",
    min,
    max,
    step,
    value: initValue ?? min,
  });

  slider.addEventListener("input", () => {
    valueLabel.textContent = fmt(slider.value);
  });

  const hintNode = hint
    ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, hint)
    : null;

  const root = el("label", { style: "display:flex; flex-direction:column; gap:2px" }, [
    el("div", { style: "display:flex; flex-direction:column; gap:2px; margin-bottom:4px" }, [
      el("div", { style: "display:flex; align-items:center; gap:6px; flex-wrap:wrap" }, [
        el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, label),
      ]),
      hintNode,
    ]),
    el("div", { style: "display:flex; align-items:center; gap:10px; padding:4px 0" }, [
      slider,
      valueLabel,
    ]),
  ]);

  return {
    root,
    getValue: () => {
      const raw = parseFloat(slider.value);
      return Number.isNaN(raw) ? (initValue ?? min) : raw;
    },
    setValue: (v) => {
      slider.value = v;
      valueLabel.textContent = fmt(v);
    },
  };
}

// ── Toggle (bool) ─────────────────────────────────────────────────────────────
function makeToggle({ label, hint, initValue, disabled, disabledHint }) {
  const select = el("select", {
    class: "select",
    disabled: disabled || false,
  }, [
    el("option", { value: "true",  selected: initValue === true  ? "selected" : null }, "включено"),
    el("option", { value: "false", selected: initValue !== true  ? "selected" : null }, "выключено"),
  ]);

  const hintText = (disabled && disabledHint) ? disabledHint : hint;
  const hintNode = hintText
    ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, hintText)
    : null;

  const root = el("label", { style: "display:flex; flex-direction:column; gap:2px" }, [
    el("div", { style: "display:flex; flex-direction:column; gap:2px; margin-bottom:4px" }, [
      el("div", { style: "display:flex; align-items:center; gap:6px; flex-wrap:wrap" }, [
        el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, label),
      ]),
      hintNode,
    ]),
    select,
  ]);

  return {
    root,
    getValue: () => disabled ? initValue : (select.value === "true"),
  };
}

// ── Checkbox row (for silent_states) ─────────────────────────────────────────
function makeCheckboxRow({ label, checked, disabled, hint }) {
  const cb = el("input", {
    type: "checkbox",
    disabled: disabled || false,
    style: "cursor:" + (disabled ? "not-allowed" : "pointer"),
  });
  cb.checked = !!checked;

  const hintNode = hint
    ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3; margin-left:6px" }, hint)
    : null;

  const root = el("label", {
    style: "display:flex; align-items:center; gap:6px; cursor:" + (disabled ? "not-allowed" : "pointer"),
  }, [
    cb,
    el("span", { style: "font-size:12px; color:var(--text)" }, label),
    hintNode,
  ]);

  return {
    root,
    getValue: () => disabled ? true : cb.checked,
  };
}

// ── Card builder ──────────────────────────────────────────────────────────────
function makeCard(title, badgeText, bodyChildren) {
  return el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, title),
      el("span", { class: "caps mono dim" }, badgeText),
    ]),
    el("div", { class: "card-body" }, [
      el("div", { class: "field-grid" }, bodyChildren),
    ]),
  ]);
}

// ── Per-state speed key map ───────────────────────────────────────────────────
// Each preset has a different "speed" parameter name and range.
const STATE_SPEED = {
  breathe:     { key: "period_ms",      min: 1000, max: 10000, label: "Период дыхания, мс" },
  accent:      { key: "period_ms",      min: 300,  max: 3000,  label: "Период акцента, мс" },
  attentive:   { key: "wave_period_ms", min: 100,  max: 2000,  label: "Период волны, мс" },
  think_pulse: { key: "flash_ms",       min: 100,  max: 3000,  label: "Интервал вспышки, мс" },
  wake_bloom:  { key: "period_ms",      min: 1000, max: 8000,  label: "Период расцвета, мс" },
};

// Human-readable preset labels
const STATE_LABELS = {
  breathe:     "breathe — покой",
  accent:      "accent — детекция",
  attentive:   "attentive — слушание",
  think_pulse: "think_pulse — раздумье",
  wake_bloom:  "wake_bloom — пробуждение",
};

// All preset names in display order
const STATE_KEYS = ["breathe", "accent", "attentive", "think_pulse", "wake_bloom"];

// ── Build one state table row ───────────────────────────────────────────────
function buildStateRow(stateKey, stateData) {
  const speed = STATE_SPEED[stateKey];
  const isAttentive = stateKey === "attentive";
  const isThinkPulse = stateKey === "think_pulse";

  // База — every state except attentive has base_pct
  const hasBase = !isAttentive;
  let baseCtl = null;
  let baseCell;
  if (hasBase) {
    baseCtl = makeSlider({
      label: "Низ, %",
      min: 0, max: 100, step: 1,
      initValue: stateData.base_pct ?? 0,
    });
    baseCell = el("td", {}, baseCtl.root);
  } else {
    baseCell = el("td", {}, el("span", { style: "color:var(--dim)" }, "—"));
  }

  // Пик (≤71%) — hard UI cap; loaded values above 71 clamp to 71 on the slider
  const peakCtl = makeSlider({
    label: "Пик, %",
    min: 0, max: 71, step: 1,
    initValue: Math.min(stateData.peak_pct ?? 50, 71),
  });
  const peakCell = el("td", {}, peakCtl.root);

  // Скорость — slider + sub-label with the real Flora.json field name
  const speedVal = stateData[speed.key] ?? Math.round((speed.min + speed.max) / 2);
  const speedCtl = makeSlider({
    label: speed.label,
    min: speed.min, max: speed.max, step: 1,
    initValue: speedVal,
  });
  const speedCell = el("td", {}, [speedCtl.root, el("div", { class: "speed-label" }, speed.key)]);

  // Вибро — attentive: disabled checkbox; think_pulse: read-only "2×" badge; others: toggle
  let vibroCtl = null;
  let vibroCell;
  if (isAttentive) {
    vibroCell = el("td", {}, el("input", { type: "checkbox", disabled: true }));
  } else if (isThinkPulse) {
    vibroCell = el("td", {}, el("span", { class: "badge" }, "2×"));
  } else {
    vibroCtl = makeToggle({
      label: "Вибро",
      initValue: stateData.vibro === true,
    });
    vibroCell = el("td", {}, vibroCtl.root);
  }

  // Показать сейчас
  const previewBtn = el("button", {
    class: "btn btn-icon btn-primary",
    title: "Показать сейчас",
    text: "▶",
  });
  const previewCell = el("td", { style: "text-align:center" }, previewBtn);

  // Getter — assembles only keys we own (no extra keys touched)
  function getValues() {
    const patch = {};
    if (baseCtl) {
      patch.base_pct = baseCtl.getValue();
    }
    patch.peak_pct = peakCtl.getValue();
    patch[speed.key] = speedCtl.getValue();

    // Vibro value: attentive → false (immutable); think_pulse → string or false; others → bool
    if (isAttentive) {
      patch.vibro = false;
    } else if (isThinkPulse) {
      patch.vibro = "double_pulse";
    } else {
      patch.vibro = vibroCtl.getValue();
    }
    return patch;
  }

  // Wire "Показать сейчас": save this row's edits to Flora.json, then trigger preview
  previewBtn.addEventListener("click", async () => {
    previewBtn.disabled = true;
    try {
      await api.post("/api/flora/config", { states: { [stateKey]: getValues() } });
      await api.post("/api/flora/state", { state: stateKey });
      toast(`Показан пресет: ${stateKey}`, "ok");
    } catch (e) {
      toast(`Ошибка сохранения конфига флоры: ${e.message}`, "bad", 5000);
    } finally {
      previewBtn.disabled = false;
    }
  });

  const row = el("tr", {}, [
    el("td", {}, STATE_LABELS[stateKey]),
    baseCell,
    peakCell,
    speedCell,
    vibroCell,
    previewCell,
  ]);

  return { row, getValues };
}

// ── SmartFlora helpers ────────────────────────────────────────────────────────

const EMOTION_LABELS = {
  curious: "curious — любопытство",
  warm:    "warm — тепло",
  unease:  "unease — тревога",
  sharp:   "sharp — острота",
  calm:    "calm — спокойствие",
};

// Build a <select> of all preset names (system + user) with blank "convention" option.
function makePresetSelect(allPresets, selected) {
  const opts = [
    el("option", { value: "" }, "— по умолчанию (naming convention)"),
    ...allPresets.map((p) =>
      el("option", { value: p, selected: selected === p ? "selected" : null }, p)
    ),
  ];
  return el("select", { class: "select" }, opts);
}

// Build the Emotion → Preset map card.
function buildEmotionMapCard(emotionMap, allPresets) {
  const selects = {};
  const rows = Object.entries(EMOTION_LABELS).map(([emotion, label]) => {
    const sel = makePresetSelect(allPresets, (emotionMap || {})[emotion] || "");
    selects[emotion] = sel;
    return el("label", { style: "display:flex; align-items:center; gap:8px; flex-wrap:wrap" }, [
      el("span", { style: "min-width:200px; font-size:12px; color:var(--text)" }, label),
      sel,
    ]);
  });

  const saveBtn = el("button", { class: "btn", style: "margin-top:10px; font-size:12px", text: "Сохранить привязку" });

  const card = el("section", { class: "card", style: "grid-column:1/-1" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Привязка эмоций Адама → пресет флоры"),
      el("span", { class: "caps mono dim" }, "flora.emotion_map"),
    ]),
    el("div", { class: "card-body" }, [
      el("div", { style: "display:flex; flex-direction:column; gap:8px" }, rows),
      saveBtn,
    ]),
  ]);

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    try {
      const patch = {};
      for (const [emotion, sel] of Object.entries(selects)) patch[emotion] = sel.value;
      await api.patch("/api/flora/emotion_map", { emotion_map: patch });
      toast("Привязка эмоций сохранена", "ok");
    } catch (e) {
      toast(`Ошибка: ${e.message}`, "bad", 5000);
    } finally {
      saveBtn.disabled = false;
    }
  });

  return card;
}

// Build inline form for creating / editing a user preset.
// onSave(name, params) is called with validated values.
function buildPresetForm(initName, initParams, onSave, onCancel) {
  initParams = initParams || {};
  const nameInput = el("input", {
    class: "input",
    type: "text",
    placeholder: "имя пресета (только latin, _)",
    value: initName || "",
    style: "width:180px",
  });

  const basePctCtl = makeSlider({ label: "Яркость: низ, %",  min: 0, max: 100, step: 1, initValue: initParams.base_pct ?? 10 });
  const peakPctCtl = makeSlider({ label: "Яркость: пик, %",  min: 0, max: 100, step: 1, initValue: initParams.peak_pct ?? 50 });
  const periodCtl  = makeSlider({ label: "Период, мс",       min: 100, max: 10000, step: 50, initValue: initParams.period_ms ?? 3000 });
  const sparkCtl   = makeSlider({ label: "Вероятность искр", min: 0, max: 1, step: 0.01, decimals: 2, initValue: initParams.spark_probability ?? 0 });
  const vibroCtl   = makeToggle({ label: "Вибро", initValue: initParams.vibro === true || initParams.vibro === "double_pulse" });

  const saveBtn   = el("button", { class: "btn",        style: "font-size:12px", text: "Сохранить" });
  const cancelBtn = el("button", { class: "btn btn-ghost", style: "font-size:12px", text: "Отмена" });

  saveBtn.addEventListener("click", () => {
    const name = nameInput.value.trim();
    if (!name) { toast("Введите имя пресета", "bad"); return; }
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) { toast("Имя: только latin, цифры, _ -", "bad"); return; }
    onSave(name, {
      base_pct:          basePctCtl.getValue(),
      peak_pct:          peakPctCtl.getValue(),
      period_ms:         periodCtl.getValue(),
      spark_probability: sparkCtl.getValue(),
      vibro:             vibroCtl.getValue(),
    });
  });
  cancelBtn.addEventListener("click", onCancel);

  return el("div", { style: "border:1px solid var(--border); border-radius:8px; padding:12px; background:var(--bg-2,var(--bg)); display:flex; flex-direction:column; gap:8px" }, [
    el("label", { style: "display:flex; flex-direction:column; gap:4px" }, [
      el("span", { style: "font-size:12px; color:var(--text)" }, "Имя"),
      nameInput,
    ]),
    basePctCtl.root, peakPctCtl.root, periodCtl.root, sparkCtl.root, vibroCtl.root,
    el("div", { style: "display:flex; gap:8px; margin-top:4px" }, [saveBtn, cancelBtn]),
  ]);
}

// Build the User Presets management section (full-width, below system presets).
function buildUserPresetsSection(userPresets, onReload) {
  let showForm = false;
  let editingName = null;

  const listContainer = el("div", { style: "display:flex; flex-direction:column; gap:8px" });
  const formContainer = el("div", {});

  function refreshList() {
    listContainer.innerHTML = "";
    const entries = Object.entries(userPresets);
    if (entries.length === 0) {
      listContainer.appendChild(el("div", { class: "muted", style: "font-size:12px" }, "Нет пользовательских пресетов"));
    }
    entries.forEach(([name, params]) => {
      const previewBtn = el("button", { class: "btn btn-ghost", style: "font-size:11px", text: "Показать" });
      const editBtn    = el("button", { class: "btn btn-ghost", style: "font-size:11px", text: "Изменить" });
      const deleteBtn  = el("button", { class: "btn btn-ghost bad", style: "font-size:11px", text: "Удалить" });

      previewBtn.addEventListener("click", async () => {
        try { await api.post(`/api/flora/presets/${encodeURIComponent(name)}/preview`); toast(`Показан: ${name}`, "ok"); }
        catch(e) { toast(e.message, "bad"); }
      });
      editBtn.addEventListener("click", () => {
        editingName = name;
        formContainer.innerHTML = "";
        formContainer.appendChild(buildPresetForm(name, params,
          async (newName, newParams) => {
            try {
              await api.put(`/api/flora/presets/${encodeURIComponent(name)}`, { name: newName, params: newParams });
              toast(`Пресет «${newName}» обновлён`, "ok");
              onReload();
            } catch(e) { toast(e.message, "bad"); }
          },
          () => { formContainer.innerHTML = ""; editingName = null; }
        ));
      });
      deleteBtn.addEventListener("click", async () => {
        if (!confirm(`Удалить пресет «${name}»?`)) return;
        try { await api.delete(`/api/flora/presets/${encodeURIComponent(name)}`); toast(`Удалён: ${name}`, "ok"); onReload(); }
        catch(e) { toast(e.message, "bad"); }
      });

      const summary = `base=${params.base_pct ?? "?"}% peak=${params.peak_pct ?? "?"}% period=${params.period_ms ?? "?"}ms`;
      listContainer.appendChild(
        el("div", { style: "display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding:6px 8px; border:1px solid var(--border); border-radius:6px" }, [
          el("span", { style: "font-size:13px; font-weight:600; min-width:120px" }, name),
          el("span", { class: "muted", style: "font-size:11px; flex:1" }, summary),
          previewBtn, editBtn, deleteBtn,
        ])
      );
    });
  }

  refreshList();

  const addBtn = el("button", { class: "btn btn-ghost", style: "font-size:12px; align-self:flex-start; margin-top:4px", text: "+ Создать пресет" });
  addBtn.addEventListener("click", () => {
    formContainer.innerHTML = "";
    editingName = null;
    formContainer.appendChild(buildPresetForm("", {},
      async (name, params) => {
        try {
          await api.post("/api/flora/presets", { name, params });
          toast(`Пресет «${name}» создан`, "ok");
          onReload();
        } catch(e) { toast(e.message, "bad"); }
      },
      () => { formContainer.innerHTML = ""; }
    ));
  });

  return el("section", { class: "card", style: "grid-column:1/-1" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Пользовательские пресеты"),
      el("span", { class: "caps mono dim" }, "flora.user_presets"),
    ]),
    el("div", { class: "card-body" }, [listContainer, addBtn, formContainer]),
  ]);
}

// Build one sequence step row.
function buildStepRow(allPresets, stepData, onDelete) {
  const presetSel = el("select", { class: "select", style: "min-width:140px" },
    allPresets.map((p) => el("option", { value: p, selected: (stepData?.preset === p) ? "selected" : null }, p))
  );
  const holdInput = el("input", {
    class: "input", type: "number", min: "50", max: "60000", step: "100",
    value: stepData?.hold_ms ?? 1000, style: "width:80px",
  });
  const cfInput = el("input", {
    class: "input", type: "number", min: "0", max: "2000", step: "10",
    placeholder: "авто", value: stepData?.crossfade_ms ?? "",
    style: "width:70px",
  });
  const delBtn = el("button", { class: "btn btn-ghost bad", style: "font-size:11px", text: "✕" });
  delBtn.addEventListener("click", onDelete);

  const row = el("div", { style: "display:flex; align-items:center; gap:6px; flex-wrap:wrap; padding:4px 0; border-bottom:1px solid var(--border)" }, [
    el("span", { class: "muted", style: "font-size:11px; min-width:40px" }, "пресет"),
    presetSel,
    el("span", { class: "muted", style: "font-size:11px" }, "держать, мс"),
    holdInput,
    el("span", { class: "muted", style: "font-size:11px" }, "fade, мс"),
    cfInput,
    delBtn,
  ]);

  return {
    row,
    getValue: () => {
      const cf = parseInt(cfInput.value, 10);
      const step = { preset: presetSel.value, hold_ms: parseInt(holdInput.value, 10) || 1000 };
      if (!isNaN(cf) && cfInput.value !== "") step.crossfade_ms = cf;
      return step;
    },
  };
}

// Build the Sequences management section.
function buildSequencesSection(sequences, allPresets, onReload) {
  const listContainer = el("div", { style: "display:flex; flex-direction:column; gap:8px" });
  const editorContainer = el("div", {});

  const stopBtn = el("button", { class: "btn btn-ghost", style: "font-size:12px", text: "⏹ Остановить" });
  stopBtn.addEventListener("click", async () => {
    try { await api.post("/api/flora/sequences/stop"); toast("Секвенция остановлена", "ok"); }
    catch(e) { toast(e.message, "bad"); }
  });

  function refreshList() {
    listContainer.innerHTML = "";
    if (!sequences.length) {
      listContainer.appendChild(el("div", { class: "muted", style: "font-size:12px" }, "Нет секвенций"));
    }
    sequences.forEach((seq) => {
      const name = seq.name || "?";
      const steps = seq.steps || [];
      const runBtn = el("button", { class: "btn", style: "font-size:11px", text: "▶ Запустить" });
      const delBtn = el("button", { class: "btn btn-ghost bad", style: "font-size:11px", text: "Удалить" });

      runBtn.addEventListener("click", async () => {
        try { await api.post(`/api/flora/sequences/${encodeURIComponent(name)}/run`); toast(`Запущена: ${name}`, "ok"); }
        catch(e) { toast(e.message, "bad"); }
      });
      delBtn.addEventListener("click", async () => {
        if (!confirm(`Удалить секвенцию «${name}»?`)) return;
        try { await api.delete(`/api/flora/sequences/${encodeURIComponent(name)}`); toast(`Удалена: ${name}`, "ok"); onReload(); }
        catch(e) { toast(e.message, "bad"); }
      });

      listContainer.appendChild(
        el("div", { style: "display:flex; align-items:center; gap:8px; flex-wrap:wrap; padding:6px 8px; border:1px solid var(--border); border-radius:6px" }, [
          el("span", { style: "font-size:13px; font-weight:600; min-width:140px" }, name),
          el("span", { class: "muted", style: "font-size:11px; flex:1" }, `${steps.length} шаг${steps.length === 1 ? "" : "ов"}`),
          runBtn, delBtn,
        ])
      );
    });
  }

  refreshList();

  // Sequence editor
  function openEditor(initName, initSteps) {
    editorContainer.innerHTML = "";
    const stepRows = [];
    const stepsContainer = el("div", { style: "display:flex; flex-direction:column; gap:4px" });

    function addStep(stepData) {
      const { row, getValue } = buildStepRow(allPresets, stepData, () => {
        const idx = stepRows.findIndex((r) => r.row === row);
        if (idx !== -1) {
          stepRows.splice(idx, 1);
          stepsContainer.removeChild(row);
        }
      });
      stepRows.push({ row, getValue });
      stepsContainer.appendChild(row);
    }

    (initSteps || [{ preset: allPresets[0] || "breathe", hold_ms: 2000 }]).forEach(addStep);

    const nameInput = el("input", {
      class: "input", type: "text", placeholder: "имя секвенции",
      value: initName || "", style: "width:200px",
    });
    const addStepBtn = el("button", { class: "btn btn-ghost", style: "font-size:12px", text: "+ Добавить шаг" });
    const saveBtn    = el("button", { class: "btn",           style: "font-size:12px", text: "Сохранить" });
    const cancelBtn  = el("button", { class: "btn btn-ghost", style: "font-size:12px", text: "Отмена" });

    addStepBtn.addEventListener("click", () => addStep(null));

    saveBtn.addEventListener("click", async () => {
      const name = nameInput.value.trim();
      if (!name) { toast("Введите имя секвенции", "bad"); return; }
      const steps = stepRows.map((r) => r.getValue());
      if (!steps.length) { toast("Добавьте хотя бы один шаг", "bad"); return; }
      try {
        if (initName) {
          await api.put(`/api/flora/sequences/${encodeURIComponent(initName)}`, { name, steps });
          toast(`Секвенция «${name}» обновлена`, "ok");
        } else {
          await api.post("/api/flora/sequences", { name, steps });
          toast(`Секвенция «${name}» создана`, "ok");
        }
        onReload();
      } catch(e) { toast(e.message, "bad"); }
    });
    cancelBtn.addEventListener("click", () => { editorContainer.innerHTML = ""; });

    editorContainer.appendChild(
      el("div", { style: "border:1px solid var(--border); border-radius:8px; padding:12px; background:var(--bg-2,var(--bg)); display:flex; flex-direction:column; gap:8px; margin-top:8px" }, [
        el("label", { style: "display:flex; flex-direction:column; gap:4px" }, [
          el("span", { style: "font-size:12px; color:var(--text)" }, "Имя секвенции"),
          nameInput,
        ]),
        el("div", { style: "font-size:12px; color:var(--muted); margin-top:4px" }, "Шаги (выполняются по порядку):"),
        stepsContainer,
        addStepBtn,
        el("div", { style: "display:flex; gap:8px; margin-top:4px" }, [saveBtn, cancelBtn]),
      ])
    );
  }

  const newBtn = el("button", { class: "btn btn-ghost", style: "font-size:12px; align-self:flex-start; margin-top:4px", text: "+ Новая секвенция" });
  newBtn.addEventListener("click", () => openEditor(null, null));

  return el("section", { class: "card", style: "grid-column:1/-1" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Последовательности анимаций"),
      el("span", { class: "caps mono dim" }, "flora.sequences"),
    ]),
    el("div", { class: "card-body" }, [
      el("div", { style: "display:flex; gap:8px; align-items:center; margin-bottom:10px; flex-wrap:wrap" }, [
        el("span", { style: "font-size:12px; color:var(--muted)" }, "Управление:"),
        stopBtn,
      ]),
      listContainer,
      newBtn,
      editorContainer,
    ]),
  ]);
}

// ── Main mount ────────────────────────────────────────────────────────────────
export function mount(target) {
  const container = el("div", { class: "col" });

  target.appendChild(el("section", { class: "col" }, [
    el("div", { class: "row", style: "flex-wrap:wrap; gap:8px" }, [
      el("div", { class: "caps" }, "Технофлора · реактивный слой света и вибрации"),
    ]),
    container,
  ]));

  async function render() {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "muted" }, [el("span", { class: "spinner" }), " загрузка…"]));

    let config;
    let floraStates;
    try {
      config = await api.get("/api/config");
      const floraConfigResp = await api.get("/api/flora/config");
      floraStates = floraConfigResp.raw_states || {};
    } catch (e) {
      container.innerHTML = "";
      container.appendChild(el("div", { class: "card" }, [
        el("div", { class: "card-body bad" }, `Ошибка загрузки Config: ${e.message}`),
      ]));
      return;
    }

    const flora = config.flora || {};
    container.innerHTML = "";

    const cardGrid = el("div", { class: "card-grid" });

    // ── 1. Глобальные ────────────────────────────────────────────────────────

    const enabledCtl = makeToggle({
      label: "Технофлора включена",
      hint: "master switch — при выключении FloraController не подписывается на EventBus",
      initValue: flora.enabled !== false,
    });

    const maxDutyCtl = makeSlider({
      label: "Безопасный потолок яркости, % сырого PWM",
      hint: "Глобальный hard cap для всех каналов флоры (свет + вибро). 100 = без ограничений. Понизьте для защиты светодиодов или БП. PWM напрямую: 70% = 2867 из 4095 тиков.",
      min: 0, max: 100, step: 1,
      initValue: flora.max_duty_pct ?? 100,
    });

    const crossfadeCtl = makeSlider({
      label: "Плавность переходов, мс",
      hint: "Длительность кроссфейда при смене пресета. 0 = мгновенно.",
      min: 0, max: 500, step: 10,
      initValue: flora.crossfade_ms ?? 200,
    });

    // Accent the max_duty slider — give it a highlighted wrapper
    const maxDutyWrapper = el("div", {
      style: [
        "grid-column: 1 / -1",         // span full width in field-grid
        "border: 1px solid var(--accent)",
        "border-radius: 8px",
        "padding: 10px 14px",
        "background: var(--bg-2, var(--bg))",
        "margin-bottom: 4px",
      ].join("; "),
    }, [maxDutyCtl.root]);

    const globalCard = el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Глобальные"),
        el("span", { class: "caps mono dim" }, "flora"),
      ]),
      el("div", { class: "card-body" }, [
        el("div", { class: "field-grid" }, [
          enabledCtl.root,
          maxDutyWrapper,
          crossfadeCtl.root,
        ]),
      ]),
    ]);
    cardGrid.appendChild(globalCard);

    // ── 2. Состояния (table) ────────────────────────────────────────────────

    const stateControllers = {};
    const statesTbody = el("tbody");
    STATE_KEYS.forEach((key) => {
      const stateData = floraStates[key] || {};
      const { row, getValues } = buildStateRow(key, stateData);
      stateControllers[key] = getValues;
      statesTbody.appendChild(row);
    });

    const statesTable = el("table", { class: "flora-table" }, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", {}, "Состояние"),
          el("th", {}, "База"),
          el("th", {}, "Пик (≤71%)"),
          el("th", {}, "Скорость"),
          el("th", {}, "Вибро"),
          el("th", {}, "Показать сейчас"),
        ]),
      ]),
      statesTbody,
    ]);

    const saveStatesBtn = el("button", {
      class: "btn btn-primary",
      style: "margin-top:12px",
      text: "Сохранить все состояния",
    });

    saveStatesBtn.addEventListener("click", async () => {
      saveStatesBtn.disabled = true;
      try {
        const states = {};
        STATE_KEYS.forEach((key) => { states[key] = stateControllers[key](); });
        await api.post("/api/flora/config", { states });
        toast("Состояния флоры сохранены", "ok");
      } catch (e) {
        toast(`Ошибка сохранения конфига флоры: ${e.message}`, "bad", 5000);
      } finally {
        saveStatesBtn.disabled = false;
      }
    });

    const statesCard = el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Состояния флоры"),
        el("span", { class: "caps mono dim" }, "flora.states"),
      ]),
      el("div", { class: "card-body" }, [statesTable, saveStatesBtn]),
    ]);
    cardGrid.appendChild(statesCard);

    // ── 3. Речь (RMS) ────────────────────────────────────────────────────────

    const speech = flora.speech || {};

    const speechBaseCtl = makeSlider({
      label: "Базовая яркость (floor RMS), %",
      min: 0, max: 100, step: 1,
      initValue: speech.base_duty_pct ?? 25,
    });
    const speechPeakCtl = makeSlider({
      label: "Пиковая яркость (peak RMS), %",
      min: 0, max: 100, step: 1,
      initValue: speech.peak_duty_pct ?? 90,
    });
    const sparkCtl = makeSlider({
      label: "Вероятность искр на пике",
      hint: "0 — нет искр, 1 — всегда. «Искра» — случайный буст канала к пику на один кадр.",
      min: 0, max: 1, step: 0.01, decimals: 2,
      initValue: speech.spark_probability ?? 0.15,
    });
    const hdmiLatCtl = makeSlider({
      label: "Компенсация задержки HDMI/ALSA, мс",
      hint: "Сдвиг светового потока, чтобы свет совпадал со звуком. ~150 мс — начальная оценка.",
      min: 0, max: 1000, step: 10,
      initValue: speech.hdmi_latency_offset_ms ?? 150,
    });
    const frameIntervalCtl = makeSlider({
      label: "Интервал RMS-кадра, мс",
      hint: "Частота отправки кадров яркости на ESP (~12.5 fps при 80 мс). Не повышайте выше 30 мс — риск перегрузки сокетов ESP.",
      min: 33, max: 500, step: 1,
      initValue: speech.frame_interval_ms ?? 80,
    });

    const speechCard = makeCard("Речь (RMS-ответ)", "flora.speech", [
      speechBaseCtl.root,
      speechPeakCtl.root,
      sparkCtl.root,
      hdmiLatCtl.root,
      frameIntervalCtl.root,
    ]);
    cardGrid.appendChild(speechCard);

    // ── 4. Вибро ─────────────────────────────────────────────────────────────

    const vibro = flora.vibro || {};

    const vibroIntensityCtl = makeSlider({
      label: "Интенсивность вибро, %",
      hint: "Потолок амплитуды вибромоторов (каналы 11–14). Не зависит от safety.motor_* — те применяются только к action.py-командам LLM.",
      min: 0, max: 100, step: 1,
      initValue: vibro.intensity_pct ?? 30,
    });

    // silent_states checkboxes — always show all 5 preset names
    const currentSilent = new Set(Array.isArray(vibro.silent_states) ? vibro.silent_states : ["attentive"]);
    const silentCheckboxes = {};
    STATE_KEYS.forEach((key) => {
      const isAttentive = key === "attentive";
      const ctl = makeCheckboxRow({
        label: key,
        checked: currentSilent.has(key),
        disabled: isAttentive,
        hint: isAttentive ? "(обязательно — защита микрофона)" : null,
      });
      silentCheckboxes[key] = ctl;
    });

    const silentLabel = el("div", { style: "display:flex; flex-direction:column; gap:2px; margin-bottom:6px" }, [
      el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, "Выкл вибро во время пресета"),
      el("span", { style: "color:var(--muted); font-size:10px" }, "attentive — обязательно (мотор наводит помехи на микрофон)"),
    ]);

    const silentBox = el("div", { style: "display:flex; flex-direction:column; gap:4px; padding:4px 0" },
      STATE_KEYS.map((k) => silentCheckboxes[k].root)
    );

    const vibroCard = el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Вибро"),
        el("span", { class: "caps mono dim" }, "flora.vibro"),
      ]),
      el("div", { class: "card-body" }, [
        el("div", { class: "field-grid" }, [
          vibroIntensityCtl.root,
        ]),
        el("div", { style: "margin-top:10px" }, [silentLabel, silentBox]),
      ]),
    ]);
    cardGrid.appendChild(vibroCard);

    // ── 5. SmartFlora: эмоции + user presets + sequences ─────────────────────

    // All preset names available for dropdowns (system + user)
    const userPresetsCfg = flora.user_presets || {};
    const allPresetNames = [
      ...STATE_KEYS,
      ...Object.keys(userPresetsCfg),
    ];

    // Emotion map card (grid-column: 1/-1 handled by its style)
    const emotionMapCard = buildEmotionMapCard(flora.emotion_map || {}, allPresetNames);
    cardGrid.appendChild(emotionMapCard);

    container.appendChild(cardGrid);

    // User presets section (full-width, outside grid)
    container.appendChild(buildUserPresetsSection(userPresetsCfg, render));

    // Sequences section (full-width, outside grid)
    container.appendChild(buildSequencesSection(flora.sequences || [], allPresetNames, render));

    // ── Save button ───────────────────────────────────────────────────────────

    const saveBtn = el("button", {
      class: "btn",
      style: "margin-top:16px; align-self:flex-start",
      text: "Сохранить",
    });

    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      try {
        // silent_states array (always include "attentive")
        const silentStates = STATE_KEYS.filter((k) => silentCheckboxes[k].getValue());

        const floraPatch = {
          enabled:         enabledCtl.getValue(),
          max_duty_pct:    maxDutyCtl.getValue(),
          crossfade_ms:    crossfadeCtl.getValue(),
          speech: {
            base_duty_pct:          speechBaseCtl.getValue(),
            peak_duty_pct:          speechPeakCtl.getValue(),
            spark_probability:      sparkCtl.getValue(),
            hdmi_latency_offset_ms: hdmiLatCtl.getValue(),
            frame_interval_ms:      frameIntervalCtl.getValue(),
          },
          vibro: {
            intensity_pct:  vibroIntensityCtl.getValue(),
            silent_states:  silentStates,
          },
        };

        await api.patch("/api/config", {
          section: "flora",
          patch: floraPatch,
        });
        toast("Технофлора сохранена", "ok");
      } catch (e) {
        toast(`Ошибка сохранения: ${e.message}`, "bad", 5000);
      } finally {
        saveBtn.disabled = false;
      }
    });

    container.appendChild(saveBtn);
  }

  render();
  // No teardown resources needed for this panel (no SSE, no animation frames)
  return undefined;
}

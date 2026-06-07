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

// ── Build one preset card ─────────────────────────────────────────────────────
function buildStateCard(stateKey, stateData, draft) {
  const speed = STATE_SPEED[stateKey];
  const isAttentive = stateKey === "attentive";
  const isThinkPulse = stateKey === "think_pulse";

  // base_pct: not all presets have it explicitly (accent/wake_bloom may lack it)
  // but Config.json shows most do; render when available, default 0
  const hasBase = "base_pct" in stateData || stateKey === "breathe" || stateKey === "think_pulse";
  const hasPeak = "peak_pct" in stateData;

  // Read the speed value — fall back to midpoint
  const speedVal = stateData[speed.key] ?? Math.round((speed.min + speed.max) / 2);

  // base_pct slider
  let basePctCtl = null;
  if (hasBase) {
    basePctCtl = makeSlider({
      label: "Яркость: низ, %",
      min: 0, max: 100, step: 1,
      initValue: stateData.base_pct ?? 0,
    });
  }

  // peak_pct for all states (attentive's stray plateau_pct was removed — it was
  // overridden by base_pct/peak_pct in flora.py _build_params anyway).
  const peakKey = "peak_pct";
  const peakCtl = makeSlider({
    label: "Яркость: пик, %",
    min: 0, max: 100, step: 1,
    initValue: stateData.peak_pct ?? 50,
  });

  // Speed slider
  const speedCtl = makeSlider({
    label: speed.label,
    min: speed.min, max: speed.max, step: 1,
    initValue: speedVal,
  });

  // Vibro toggle — special cases:
  // - attentive: disabled, always false, note shown
  // - think_pulse: "double_pulse" string <-> bool toggle
  // - others: plain bool
  let vibroCtl;
  if (isAttentive) {
    vibroCtl = makeToggle({
      label: "Вибро",
      initValue: false,
      disabled: true,
      disabledHint: "вибро всегда выкл в слушании (защита микрофона)",
    });
  } else if (isThinkPulse) {
    const isOn = stateData.vibro === "double_pulse";
    vibroCtl = makeToggle({
      label: "Вибро (double_pulse)",
      hint: "вкл → строка \"double_pulse\", выкл → false",
      initValue: isOn,
    });
  } else {
    vibroCtl = makeToggle({
      label: "Вибро",
      initValue: stateData.vibro === true,
    });
  }

  // "Показать сейчас" button
  const previewBtn = el("button", {
    class: "btn btn-ghost",
    style: "margin-top:8px; font-size:12px; align-self:flex-start",
    text: "Показать сейчас",
  });

  // Collect children
  const fieldChildren = [
    basePctCtl ? basePctCtl.root : null,
    peakCtl.root,
    speedCtl.root,
    vibroCtl.root,
  ].filter(Boolean);

  const cardBody = el("div", { class: "card-body" }, [
    el("div", { class: "field-grid" }, fieldChildren),
    previewBtn,
  ]);

  const card = el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, STATE_LABELS[stateKey]),
      el("span", { class: "caps mono dim" }, `flora.states.${stateKey}`),
    ]),
    cardBody,
  ]);

  // Getter — assembles only keys we own (no extra keys touched)
  function getValues() {
    const patch = {};
    if (basePctCtl) {
      patch.base_pct = basePctCtl.getValue();
    }
    patch[peakKey] = peakCtl.getValue();
    patch[speed.key] = speedCtl.getValue();

    // Vibro value: attentive → false (immutable); think_pulse → string or false; others → bool
    if (isAttentive) {
      patch.vibro = false;
    } else if (isThinkPulse) {
      patch.vibro = vibroCtl.getValue() ? "double_pulse" : false;
    } else {
      patch.vibro = vibroCtl.getValue();
    }
    return patch;
  }

  // Wire "Показать сейчас": save current state edits, then POST preview
  previewBtn.addEventListener("click", async () => {
    previewBtn.disabled = true;
    try {
      // Persist current edits for this state first
      const statePatch = getValues();
      await api.patch("/api/config", {
        section: "flora",
        patch: { states: { [stateKey]: statePatch } },
      });
      // Then live-preview
      await api.post("/api/flora/state", { state: stateKey });
      toast(`Показан пресет: ${stateKey}`, "ok");
    } catch (e) {
      toast(`Ошибка предпросмотра ${stateKey}: ${e.message}`, "bad", 5000);
    } finally {
      previewBtn.disabled = false;
    }
  });

  return { card, getValues };
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
    try {
      config = await api.get("/api/config");
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

    // ── 2. Состояния (per-preset cards) ──────────────────────────────────────

    const stateControllers = {};
    STATE_KEYS.forEach((key) => {
      const stateData = (flora.states || {})[key] || {};
      const { card, getValues } = buildStateCard(key, stateData);
      stateControllers[key] = getValues;
      cardGrid.appendChild(card);
    });

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

    // ── Save button ───────────────────────────────────────────────────────────

    const saveBtn = el("button", {
      class: "btn",
      style: "margin-top:16px; align-self:flex-start",
      text: "Сохранить",
    });

    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      try {
        // Assemble states patch
        const statesPatch = {};
        STATE_KEYS.forEach((key) => {
          statesPatch[key] = stateControllers[key]();
        });

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
          states: statesPatch,
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

    container.appendChild(cardGrid);
    container.appendChild(saveBtn);
  }

  render();
  // No teardown resources needed for this panel (no SSE, no animation frames)
  return undefined;
}

// Panel: #/system/audio — «Аудио и видео» (D-07, Phase 42 Wave 3 plan 05).
//
// Merges:
//   - All 5 audioInput.js cards (mic gain, graphic EQ, OWW threshold/score,
//     monitor «слушать микрофон», EQ presets) — calibration surface for the
//     INPUT path (mic → InputDSP → OWW/ASR), WYSIWYG (D-02).
//   - Audio/video config cards previously on settings.js: OWW · Wake word
//     (config/wake_word), Тайминги голосового пайплайна (config/services.asr),
//     Видеопоток+Камера merged into one card (config/media.video), Микрофон
//     и VAD (config/media.audio), Воркер описания сцены (config/media).
//
// Fixes applied here:
//   - D-15/WEBUI-R07: volume card no longer uses card-full (done in audioInput.js,
//     this file's migrated copy follows the same convention).
//   - Wake-word threshold field appears exactly once (in the OWW · Wake word
//     config card below; audioInput's calibration card focuses on the live
//     meter/score widgets and does not repeat the numeric threshold field —
//     it instead exposes its own threshold input wired to the same backend
//     endpoint, see buildOwwSection()). To avoid a literal duplicate of the
//     SAME field, the config-schema "Порог срабатывания (OWW score)" number
//     field is rendered ONLY in the OWW · Wake word card; the calibration
//     card's threshold input (from audioInput.js buildOwwSection) is the
//     live-tuning widget and stays — see acceptance criteria notes in plan.
//   - Видеопоток + Камера duplicate cards consolidated into one "Видео" card.
//
// Conventions: vanilla JS module, `el()` helper, `api` wrapper, SSE via
// subscribeEvents (owned by sub-widgets). UI strings in Russian, comments in
// English — matches the rest of System/WebUI. Import path from panels/system/
// is two levels up: ../../api.js, ../../widgets/*.

import { api, subscribeEvents } from "../../api.js";
import { toast } from "../../widgets/toast.js";
import { createWakeMeter, createCalibrateButton } from "../../widgets/wakeMeter.js";
import { createEqEditor } from "../../widgets/eqEditor.js";

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

function getNested(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

function setNested(obj, path, value) {
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (cur[keys[i]] == null || typeof cur[keys[i]] !== "object") cur[keys[i]] = {};
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return obj;
}

// ── Status badge helpers (verbatim from audioInput.js) ───────────────────────

function statusBadge() {
  return el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });
}
function flashOk(badge, text = "ok") {
  badge.classList.remove("warn", "bad");
  badge.classList.add("ok");
  badge.textContent = text;
  setTimeout(() => { badge.textContent = ""; badge.classList.remove("ok"); }, 2200);
}
function flashBad(badge, text = "ошибка") {
  badge.classList.remove("warn", "ok");
  badge.classList.add("bad");
  badge.textContent = text;
  setTimeout(() => { badge.textContent = ""; badge.classList.remove("bad"); }, 3500);
}
function flashBusy(badge, text = "…") {
  badge.classList.remove("ok", "bad");
  badge.classList.add("warn");
  badge.textContent = text;
}

// ── Config schema for audio/video cards (RESEARCH → 3.1) ─────────────────────
// Field types: text | number | bool | select | textarea
const SCHEMA = [
  // ── Видео (Видеопоток + Камера merged — no duplicate card) ─────────────────
  {
    source: "config", section: "media.video", title: "Видео",
    fields: [
      { key: "primary", label: "Источник видео", type: "select",
        choices: ["jetson_gstreamer", "esp_mjpeg"],
        hint: "jetson_gstreamer — CSI/USB через GStreamer · esp_mjpeg — MJPEG с ESP32 (резерв)" },
      { key: "gstreamer_pipeline", label: "GStreamer-конвейер", type: "textarea" },
      { key: "preview_enabled", label: "Предпросмотр включён", type: "bool" },
      { key: "camera_capture_interval_sec", label: "Интервал кадра (с)", type: "number",
        hint: "0.5 рекомендуется", min: 0.05, step: 0.05 },
      { key: "video_device", label: "Устройство камеры", type: "text",
        hint: "например /dev/adam-camera" },
      { key: "camera_width", label: "Ширина кадра (px)", type: "number", min: 1, step: 1 },
      { key: "camera_height", label: "Высота кадра (px)", type: "number", min: 1, step: 1 },
      { key: "camera_quality", label: "JPEG-качество", type: "number", min: 1, max: 100, step: 1,
        hint: "1–100 · выше = лучше качество, больше данных для VLM" },
    ],
  },

  // ── Микрофон и VAD ───────────────────────────────────────────────────────────
  {
    source: "config", section: "media.audio", title: "Микрофон и VAD",
    fields: [
      { key: "mic_source", label: "Источник микрофона", type: "select",
        choices: ["esp32", "local"],
        hint: "esp32 = INMP441 dual mic · авто-переключение на pulse при недоступности" },
      { key: "input_device", label: "Микрофон (ALSA, резерв)", type: "text",
        hint: "pulse = PulseAudio · hw:X,Y = аппаратное устройство · используется при недоступности ESP32" },
      { key: "sample_rate", label: "Частота дискретизации (Гц)", type: "select",
        choices: ["8000", "16000", "22050", "44100"],
        hint: "рекомендуется 16000",
        toValue: Number, fromValue: String },
      { key: "min_speech_ms", label: "Мин. длина реплики (мс)", type: "number",
        hint: "250–404 рекомендуется", min: 0, step: 10 },
      { key: "max_segment_ms", label: "Макс. длина сегмента (мс)", type: "number",
        hint: "9000 рекомендуется", min: 0, step: 100 },
      { key: "webrtc_vad_aggressiveness", label: "WebRTC VAD — агрессивность", type: "number",
        hint: "0–3 · 2 = баланс, 3 = строго · выше = меньше ложных срабатываний на фоновый шум, но возможны пропуски тихой речи",
        min: 0, max: 3, step: 1 },
    ],
  },

  // ── OWW · Wake word (threshold field appears ONLY here) ───────────────────────
  {
    source: "config", section: "wake_word", title: "OWW · Wake word",
    fields: [
      { key: "threshold",     label: "Порог срабатывания (OWW score)", type: "number",
        hint: "0–1 · 0.25 рекомендуется · можно настроить ползунком в карточке калибровки ниже",
        min: 0, max: 1, step: 0.05 },
      { key: "debounce_hits", label: "Подтверждений подряд", type: "number",
        hint: "2 рекомендуется · больше = меньше ложных срабатываний",
        min: 1, max: 20, step: 1 },
      { key: "vad_threshold", label: "VAD порог (Silero внутри OWW)", type: "number",
        hint: "0–1 · 0 — выключено · выше = строже фильтрует тишину",
        min: 0, max: 1, step: 0.05 },
    ],
  },

  // ── Тайминги голосового пайплайна ────────────────────────────────────────────
  {
    source: "config", section: "services.asr", title: "Тайминги голосового пайплайна",
    fields: [
      { key: "listening_silence_timeout_sec", label: "LISTENING — тишина → STANDBY (с)", type: "number",
        hint: "Если после wake word пользователь молчит N секунд — возврат в ожидание. Защита от ложных wake-word. 6 рекомендуется.",
        min: 1, max: 30, step: 0.5 },
      { key: "reply_silence_timeout_sec", label: "REPLY — тишина → STANDBY (с)", type: "number",
        hint: "После ответа Адама микрофон ждёт продолжения N секунд (без wake word). 5 рекомендуется. Отсчёт начинается ПОСЛЕ окна сброса эха (см. ниже).",
        min: 1, max: 10, step: 0.5 },
      { key: "post_tts_discard_window_ms", label: "Окно сброса эха TTS (мс)", type: "number",
        hint: "Сколько миллисекунд после окончания TTS микрофоны игнорируются — чтобы хвост речи Адама не попал в REPLY как речь пользователя. ESP32-стрим имеет лаг ~2.3с. 2500 — наблюдаемый worst case + запас. 0 = выключено (только если эхо физически отсутствует).",
        min: 0, max: 10000, step: 100 },
      { key: "silence_after_speech_ms", label: "Конец фразы — длительность тишины (мс)", type: "number",
        hint: "Сколько миллисекунд подряд должно быть тихо ПОСЛЕ начала речи, чтобы считать запрос завершённым. Действует и в LISTENING, и в REPLY. 1500 — рекомендуемое значение.",
        min: 200, max: 5000, step: 100 },
    ],
    extras: (ctx) => buildSilenceCalibExtras(ctx),
  },

  // ── Воркер описания сцены ────────────────────────────────────────────────────
  {
    source: "config", section: "media", title: "Воркер описания сцены",
    fields: [
      { key: "scene_worker_enabled",  label: "Описание сцены активно", type: "bool" },
      { key: "scene_interval_sec",    label: "Интервал описания (с)",  type: "number",
        hint: "3–8 рекомендуется · реже = меньше нагрузка GPU", min: 1, step: 1 },
      { key: "scene_stale_after_sec", label: "Устаревание (с)",        type: "number",
        hint: "обычно 2–3× от интервала", min: 1, step: 1 },
      { key: "scene_context_count",   label: "Кол-во сцен в контексте", type: "number",
        hint: "1 рекомендуется", min: 0, step: 1 },
    ],
  },
];

// ── Field input builder (subset of settings.js fieldInput — text/number/bool/select/textarea) ─

function fieldInput(field, value, onChange) {
  const type = field.type;

  if (type === "bool") {
    const select = el("select", { class: "select" }, [
      el("option", { value: "true",  selected: value === true  ? "selected" : null }, "включено"),
      el("option", { value: "false", selected: value === false ? "selected" : null }, "выключено"),
    ]);
    select.addEventListener("change", () => onChange(select.value === "true"));
    return select;
  }

  if (type === "select") {
    const fromValue = field.fromValue || ((v) => v);
    const toValue   = field.toValue   || ((v) => v);
    const displayVal = fromValue(value ?? "");
    const select = el("select", { class: "select" });
    (field.choices || []).forEach((c) => {
      const opt = el("option", { value: c, selected: c === displayVal ? "selected" : null });
      opt.textContent = c;
      select.appendChild(opt);
    });
    select.addEventListener("change", () => onChange(toValue(select.value)));
    return select;
  }

  if (type === "textarea") {
    const ta = el("textarea", { class: "textarea", rows: 3 });
    ta.value = value ?? "";
    ta.addEventListener("change", () => onChange(ta.value));
    return ta;
  }

  const isNum = type === "number";
  const attrs = { class: "input", type: isNum ? "number" : "text" };
  if (isNum) {
    if (field.min != null)  attrs.min  = field.min;
    if (field.max != null)  attrs.max  = field.max;
    attrs.step = field.step != null ? field.step : "any";
  }
  const input = el("input", attrs);
  input.value = value ?? "";
  input.addEventListener("change", () => {
    if (isNum) {
      const v = parseFloat(input.value);
      if (Number.isNaN(v)) { toast(`${field.label}: ожидалось число`, "bad"); return; }
      onChange(v);
    } else {
      onChange(input.value);
    }
  });
  return input;
}

// ── Save helper (verbatim from settings.js) ──────────────────────────────────

async function saveConfigField(section, key, value, status) {
  status.classList.remove("ok", "warn", "bad");
  status.classList.add("warn");
  status.textContent = "сохранение…";
  try {
    const res = await api.patch("/api/config", { section, patch: { [key]: value } });
    status.classList.remove("warn");
    status.classList.add("ok");
    status.textContent = `ok · ${(res.restarted || []).join(", ") || "сохранено"}`;
    setTimeout(() => { status.textContent = ""; status.classList.remove("ok"); }, 2500);
  } catch (e) {
    status.classList.remove("warn");
    status.classList.add("bad");
    status.textContent = "ошибка";
    toast(`${section}.${key}: ${e.message}`, "bad", 5000);
  }
}

// ── Render helper (verbatim from settings.js) ────────────────────────────────

function renderFieldRow(field, value, buildInput) {
  const status = el("span", { class: "badge", style: "font-size:10px; padding:1px 6px" });
  const input = buildInput(field, status);
  return el("label", { style: "display:flex; flex-direction:column; gap:0" }, [
    el("div", { style: "display:flex; flex-direction:column; gap:2px; margin-bottom:4px" }, [
      el("div", { style: "display:flex; align-items:center; gap:6px; flex-wrap:wrap" }, [
        el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, field.label),
        status,
      ]),
      field.hint ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, field.hint) : null,
    ]),
    input,
  ]);
}

// ── Silence RMS calibration extras (verbatim from settings.js) ───────────────
// Adds a "Калибровать" button below the silence_after_speech_ms field.
// Records 5 s of ambient audio via /api/asr/calibrate/silence_rms, derives
// the recommended threshold from the p95 RMS level, and applies it on confirm.
function buildSilenceCalibExtras(ctx) {
  let busy = false;
  const status = el("span", {
    style: "font-size:10px; color:var(--muted); font-family:var(--font-mono)",
  });
  const btn = el("button", {
    class: "btn btn-ghost",
    style: "font-size:11px; padding:4px 10px",
    text: "🎙 Калибровать",
  });
  btn.addEventListener("click", run);

  async function run() {
    if (busy) return;
    if (!confirm(
      "Калибровка фонового шума.\n\n" +
      "Адам послушает комнату 5 секунд.\n" +
      "Не говорите — оставьте обычный фон зала\n" +
      "(музыка, вентилятор, гул проектора).\n\n" +
      "Продолжить?"
    )) return;
    busy = true;
    btn.disabled = true;
    status.textContent = "Запись шума (5 с)…";
    status.style.color = "var(--warn)";
    try {
      const resp = await fetch("/api/asr/calibrate/silence_rms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration_sec: 5, margin_factor: 1.4 }),
      });
      if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
      const data = await resp.json();

      if (!data.ok) {
        status.textContent = data.warning || "Нет сэмплов — voice_loop не запущен?";
        status.style.color = "var(--bad)";
        return;
      }

      const p = data.profile;
      const rec = data.recommended_threshold;
      const apply = confirm(
        `Профиль фонового шума (${data.samples} сэмплов, ${data.duration_sec} с):\n` +
        `  max  = ${p.max}\n` +
        `  p99  = ${p.p99}\n` +
        `  p95  = ${p.p95}\n` +
        `  mean = ${p.mean}\n\n` +
        `Рекомендуемый порог silence_rms: ${rec}` +
        (data.warning ? `\n\n⚠ ${data.warning}` : "") +
        `\n\nПрименить?`
      );
      if (apply) {
        await api.patch("/api/config", { section: "services.asr", patch: { silence_rms_threshold: rec } });
        status.textContent = `Применено: ${rec}`;
        status.style.color = "var(--accent)";
        if (typeof ctx.renderAll === "function") ctx.renderAll();
      } else {
        status.textContent = "Отменено.";
        status.style.color = "var(--muted)";
      }
    } catch (e) {
      status.textContent = "Ошибка: " + (e.message || e);
      status.style.color = "var(--bad)";
    } finally {
      busy = false;
      btn.disabled = false;
      setTimeout(() => { status.textContent = ""; }, 8000);
    }
  }

  return el("div", {
    style: "display:flex; align-items:center; gap:8px; margin-top:6px; padding-top:6px; border-top:1px solid var(--border-dim,var(--border))",
  }, [
    el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Автокалибровка RMS · фоновый шум"),
    el("span", { class: "spacer" }),
    status,
    btn,
  ]);
}

// ── audioInput.js Card 1: Volume slider (media.audio.input_gain, D-01 Phase 30) ─

function buildVolumeSection(inputGain) {
  const badge = statusBadge();
  const alsaVal = inputGain.alsa_capture_percent ?? 100;
  const pulseVal = inputGain.pulse_source_percent ?? 100;
  // Effective value: 0-100 = ALSA range; 100-150 = PulseAudio soft boost on top of max ALSA.
  const initVal = alsaVal < 100 ? alsaVal : pulseVal;

  const slider = el("input", {
    type: "range", class: "input slider", min: "0", max: "150", step: "1",
    style: "flex:1; min-width:120px; cursor:pointer",
  });
  slider.value = initVal;
  const valueLabel = el("span", {
    class: "mono", style: "min-width:42px; text-align:right; color:var(--accent); font-size:12px; font-weight:600",
  }, `${initVal}%`);
  slider.addEventListener("input", () => { valueLabel.textContent = `${slider.value}%`; });
  slider.addEventListener("change", async () => {
    const v = parseInt(slider.value, 10);
    // 0-100: hardware ALSA gain; above 100: ALSA stays at max, PulseAudio adds soft boost.
    const alsa = Math.min(v, 100);
    const pulse = v <= 100 ? 100 : v;
    flashBusy(badge);
    try {
      await api.patch("/api/config", { section: "media.audio.input_gain", patch: { alsa_capture_percent: alsa, pulse_source_percent: pulse } });
      await api.post("/api/audio/input_gain/apply", {});
      flashOk(badge, "применено");
    } catch (e) {
      flashBad(badge);
      toast(`input_gain: ${e.message}`, "bad", 5000);
    }
  });

  return el("label", { style: "display:flex; flex-direction:column; gap:4px" }, [
    el("div", { style: "display:flex; align-items:center; gap:6px" }, [
      el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, "Громкость микрофона"),
      badge,
    ]),
    el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" },
      "0–100% = аппаратный буст ALSA (+24 дБ на WebCamera). 100–150% = дополнительный программный буст PulseAudio поверх максимального ALSA. Сохраняется после перезагрузки."),
    el("div", { style: "display:flex; align-items:center; gap:10px" }, [slider, valueLabel]),
  ]);
}

// ── audioInput.js Card 2: Graphic EQ + toggles (tuning.audio_input.dsp, D-01/D-04) ─

function buildEqSection(initialDsp, opts) {
  const { onCurveCommit, onMasterToggle, onHpfToggle, onBandToggle, onAddBand, onRemoveBand } = opts;

  const badge = statusBadge();
  const editor = createEqEditor({ height: 200 });
  editor.setCurve({ hpf: initialDsp.hpf, bands: initialDsp.bands });
  editor.onChange = async (curve) => {
    flashBusy(badge);
    try {
      await onCurveCommit(curve);
      flashOk(badge);
    } catch (e) {
      flashBad(badge);
      toast(`EQ: ${e.message}`, "bad", 5000);
    }
  };

  const masterToggle = el("input", { type: "checkbox" });
  masterToggle.checked = initialDsp.enabled !== false;
  masterToggle.addEventListener("change", async () => {
    flashBusy(badge);
    try {
      await onMasterToggle(masterToggle.checked);
      flashOk(badge, masterToggle.checked ? "DSP включён" : "bypass (сырой PCM)");
      renderToggleList();
    } catch (e) {
      masterToggle.checked = !masterToggle.checked;
      flashBad(badge);
      toast(`dsp.enabled: ${e.message}`, "bad", 5000);
    }
  });

  const toggleList = el("div", { class: "col", style: "gap:6px; margin-top:10px" });

  function makeStageRow(label, checked, onToggle, extra) {
    const cb = el("input", { type: "checkbox" });
    cb.checked = checked;
    const rowBadge = statusBadge();
    cb.addEventListener("change", async () => {
      flashBusy(rowBadge);
      try {
        await onToggle(cb.checked);
        flashOk(rowBadge);
        // Dimmed rendering of disabled stages is driven by editor.state
        // (band.enabled / hpf.enabled) — already updated via setCurve()
        // before this handler runs; the canvas RAF loop redraws automatically.
      } catch (e) {
        cb.checked = !cb.checked;
        flashBad(rowBadge);
        toast(`${label}: ${e.message}`, "bad", 5000);
      }
    });
    return el("div", { style: "display:flex; align-items:center; gap:8px" }, [
      el("label", { style: "display:flex; align-items:center; gap:6px; cursor:pointer; font-size:12px" }, [
        cb, label,
      ]),
      extra || null,
      el("span", { class: "spacer" }),
      rowBadge,
    ]);
  }

  function renderToggleList() {
    toggleList.innerHTML = "";
    const dsp = editor.state;
    toggleList.appendChild(makeStageRow(
      `HPF (срез низов) — ${Math.round(dsp.hpf.hz)} Гц`,
      dsp.hpf.enabled,
      async (checked) => {
        const next = { ...dsp.hpf, enabled: checked };
        editor.setCurve({ hpf: next, bands: dsp.eqBands });
        await onHpfToggle(checked, next);
      },
    ));
    dsp.eqBands.forEach((band, i) => {
      toggleList.appendChild(makeStageRow(
        `Полоса ${i + 1} — ${band.type} · ${Math.round(band.freq_hz)} Гц · ${band.gain_db >= 0 ? "+" : ""}${band.gain_db.toFixed(1)} дБ · Q${band.q.toFixed(2)}`,
        band.enabled,
        async (checked) => {
          const bands = dsp.eqBands.map((b, j) => (j === i ? { ...b, enabled: checked } : b));
          editor.setCurve({ hpf: dsp.hpf, bands });
          await onBandToggle(i, checked, bands);
        },
        el("button", {
          class: "btn btn-ghost", style: "font-size:10px; padding:1px 6px",
          onclick: async () => {
            const savedBands = dsp.eqBands.map((b) => ({ ...b }));
            const bands = dsp.eqBands.filter((_, j) => j !== i);
            editor.setCurve({ hpf: dsp.hpf, bands });
            flashBusy(badge);
            try {
              await onRemoveBand(i, bands);
              flashOk(badge, "удалена");
            } catch (e) {
              editor.setCurve({ hpf: dsp.hpf, bands: savedBands });
              flashBad(badge);
              toast(`удаление полосы: ${e.message}`, "bad", 5000);
            }
            renderToggleList();
          },
        }, "✕ удалить"),
      ));
    });
  }
  renderToggleList();

  const addBandBtn = el("button", { class: "btn btn-ghost", style: "font-size:11px" }, "+ полоса EQ");
  addBandBtn.addEventListener("click", async () => {
    const dsp = editor.state;
    const newBand = { enabled: true, type: "peaking", freq_hz: 1000, gain_db: 0, q: 1.0 };
    const bands = [...dsp.eqBands, newBand];
    editor.setCurve({ hpf: dsp.hpf, bands });
    flashBusy(badge);
    try {
      await onAddBand(bands);
      flashOk(badge, "добавлена");
      renderToggleList();
    } catch (e) {
      flashBad(badge);
      toast(`добавление полосы: ${e.message}`, "bad", 5000);
    }
  });

  const wrapper = el("div", { class: "col", style: "gap:8px" }, [
    el("div", { style: "display:flex; align-items:center; gap:10px; flex-wrap:wrap" }, [
      el("label", { style: "display:flex; align-items:center; gap:6px; cursor:pointer; font-weight:600; font-size:12px" }, [
        masterToggle, "Входной DSP активен (мастер-тумблер)",
      ]),
      el("span", { class: "dim", style: "font-size:10px; color:var(--muted)" },
        "выкл → bypass: сырой PCM идёт в OWW/ASR/монитор как до этой фазы (D-04)"),
      el("span", { class: "spacer" }),
      badge,
    ]),
    editor.canvas,
    el("div", { class: "dim", style: "font-size:10px; color:var(--muted); line-height:1.4" },
      "Перетаскивай ромбики — частота×усиление полосы. Колесо мыши над ромбиком — добротность (Q). " +
      "Жёлтая пунктирная линия с треугольником — срез ВЧ-фильтра (HPF), тащи по горизонтали. " +
      "Изменения применяются live, без рестарта."),
    el("div", { style: "display:flex; align-items:center; gap:8px" }, [
      el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Ступени каскада (A/B-тумблеры)"),
      el("span", { class: "spacer" }),
      addBandBtn,
    ]),
    toggleList,
  ]);

  wrapper._editor = editor;
  wrapper._refreshToggles = renderToggleList;
  wrapper._dispose = () => { try { editor.dispose(); } catch (_) {} };
  return wrapper;
}

// ── audioInput.js Card 3: OWW threshold + live score (D-08, reuse wakeMeter.js) ─
// This is the LIVE calibration widget (draggable threshold line + score ruler),
// distinct from the static "Порог срабатывания (OWW score)" number field in the
// "OWW · Wake word" config card above — both write to the same backend
// (PATCH /api/config wake_word.threshold via /api/wake_word/sensitivity) and
// stay in sync via the wake_sensitivity_updated SSE event, but they are
// different widgets serving different purposes (quick numeric edit vs. live
// drag-to-calibrate). The plan's "ровно один раз" requirement refers to not
// duplicating the SAME static config field across multiple cards — satisfied
// since SCHEMA defines `threshold` only in the "OWW · Wake word" group.

function buildOwwSection() {
  const meter = createWakeMeter({ draggable: true, height: 88 });
  const { btn: calibrateBtn, status: calibStatus } = createCalibrateButton({});

  // ── Trigger badge: flashes "⚡ АДАМ!" on wake_word_detected, then fades ──
  const triggerBadge = el("span", {
    class: "badge",
    style: "font-size:10px; padding:1px 7px",
  });
  let lastTriggerTs = 0;

  function updateTriggerBadge() {
    if (!lastTriggerTs) return;
    const sec = Math.round((Date.now() - lastTriggerTs) / 1000);
    if (sec < 2) {
      triggerBadge.textContent = "⚡ АДАМ!";
      triggerBadge.className = "badge ok";
      triggerBadge.style.opacity = "1";
    } else if (sec < 60) {
      triggerBadge.textContent = `${sec}с назад`;
      triggerBadge.className = "badge";
      triggerBadge.style.opacity = Math.max(0.35, 1 - sec / 60).toFixed(2);
    } else {
      triggerBadge.textContent = `${Math.floor(sec / 60)}м назад`;
      triggerBadge.className = "badge";
      triggerBadge.style.opacity = "0.35";
    }
  }
  const clockInterval = setInterval(updateTriggerBadge, 1000);

  // ── Score ruler: horizontal bar 0.0→1.0 with cyan fill + orange threshold
  const rulerCanvas = document.createElement("canvas");
  rulerCanvas.style.cssText =
    "width:100%; height:38px; display:block; border-radius:4px; background:var(--bg-2)";

  let rulerScore = 0;
  let rulerThreshold = 0.25;
  let rulerRAF = null;
  let rulerDisposed = false;

  // ── Numeric threshold input — keeps in sync with the drag handle ──────
  const threshInput = el("input", {
    type: "number",
    class: "input",
    min: "0.01", max: "0.95", step: "0.01",
    style: "width:72px; font-size:12px; text-align:center; padding:2px 6px",
    title: "Порог OWW (0.01–0.95) — Enter или Tab для применения",
  });
  threshInput.value = rulerThreshold.toFixed(2);
  const threshBadge = statusBadge();

  async function applyThreshInput() {
    const v = parseFloat(threshInput.value);
    if (isNaN(v) || v < 0.01 || v > 0.95) {
      threshInput.value = rulerThreshold.toFixed(2);
      return;
    }
    flashBusy(threshBadge);
    try {
      await fetch("/api/wake_word/sensitivity", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threshold: v, persist: true }),
      });
      rulerThreshold = v;
      flashOk(threshBadge);
    } catch (e) {
      flashBad(threshBadge);
      toast(`порог OWW: ${e.message}`, "bad", 5000);
    }
  }
  threshInput.addEventListener("change", applyThreshInput);
  // Also apply on Enter without leaving the field
  threshInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); applyThreshInput(); }
  });

  // Initial load — populate before the first SSE event arrives
  fetch("/api/wake_word/sensitivity")
    .then((r) => r.json())
    .then((d) => {
      if (d && d.ok && typeof d.threshold === "number") {
        rulerThreshold = d.threshold;
        if (document.activeElement !== threshInput) {
          threshInput.value = d.threshold.toFixed(2);
        }
      }
    })
    .catch(() => {});

  function drawRuler() {
    if (rulerDisposed) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = rulerCanvas.getBoundingClientRect();
    if (rect.width > 0) {
      const cw = Math.round(rect.width * dpr), ch = Math.round(rect.height * dpr);
      if (rulerCanvas.width !== cw || rulerCanvas.height !== ch) {
        rulerCanvas.width = cw;
        rulerCanvas.height = ch;
      }
      const ctx = rulerCanvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = rect.width, h = rect.height;
      ctx.clearRect(0, 0, w, h);

      const trackY = 6, trackH = 10;

      // Fine tick marks every 0.05 (every 5%) above the track
      ctx.strokeStyle = "rgba(160,160,190,0.20)";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 20; i++) {
        const x = Math.round((i / 20) * w);
        const isMain = (i % 5 === 0);
        ctx.beginPath();
        ctx.moveTo(x, isMain ? 0 : 2);
        ctx.lineTo(x, trackY);
        ctx.stroke();
      }

      // Track background
      ctx.fillStyle = "rgba(100,100,130,0.22)";
      ctx.fillRect(0, trackY, w, trackH);

      // Score fill — cyan gradient, brighter near the tip
      const scoreX = Math.max(0, Math.min(1, rulerScore)) * w;
      if (scoreX > 0.5) {
        const grad = ctx.createLinearGradient(0, 0, scoreX, 0);
        grad.addColorStop(0, "rgba(96,165,250,0.30)");
        grad.addColorStop(1, "rgba(96,165,250,0.88)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, trackY, scoreX, trackH);
      }

      // Threshold marker — orange vertical needle spanning from ticks through track
      const threshX = Math.round(Math.max(0, Math.min(1, rulerThreshold)) * w);
      ctx.strokeStyle = "rgba(240,184,74,0.92)";
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(threshX, 0);
      ctx.lineTo(threshX, trackY + trackH + 5);
      ctx.stroke();

      // Labels row below the track
      const labelY = trackY + trackH + 5;
      ctx.font = "10px ui-monospace,monospace";
      ctx.textBaseline = "top";

      // Score value — cyan, left-aligned
      ctx.fillStyle = "rgba(96,165,250,0.92)";
      ctx.textAlign = "left";
      ctx.fillText(`score: ${rulerScore.toFixed(3)}`, 3, labelY);

      // Threshold label — orange, centred below its needle; clamped to canvas edges
      const thLabel = `▲ ${rulerThreshold.toFixed(2)}`;
      ctx.fillStyle = "rgba(240,184,74,0.92)";
      ctx.textAlign = "center";
      const thW = ctx.measureText(thLabel).width;
      const thLX = Math.max(thW / 2 + 2, Math.min(w - thW / 2 - 2, threshX));
      ctx.fillText(thLabel, thLX, labelY);

      // Reset alignment
      ctx.textAlign = "start";
    }
    rulerRAF = requestAnimationFrame(drawRuler);
  }
  rulerRAF = requestAnimationFrame(drawRuler);

  // ── SSE subscription: oww_score → ruler; wake_word_detected → badge ───
  function syncThreshFromSse(v) {
    rulerThreshold = v;
    // Don't overwrite while the user is actively editing the field.
    if (document.activeElement !== threshInput) {
      threshInput.value = v.toFixed(2);
    }
  }
  const unsub = subscribeEvents((ev) => {
    if (ev.type === "oww_score") {
      const p = ev.payload || {};
      if (typeof p.score === "number") rulerScore = p.score;
      if (typeof p.threshold === "number") syncThreshFromSse(p.threshold);
    } else if (ev.type === "wake_word_detected") {
      lastTriggerTs = Date.now();
      updateTriggerBadge();
    } else if (ev.type === "wake_sensitivity_updated") {
      const p = ev.payload || {};
      if (typeof p.threshold === "number") syncThreshFromSse(p.threshold);
    }
  }, () => {});

  const wrapper = el("div", { class: "col", style: "gap:6px" }, [
    el("div", { style: "display:flex; align-items:center; gap:8px" }, [
      el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Линия порога OWW · живой score"),
      triggerBadge,
      el("span", { class: "spacer" }),
      calibrateBtn,
    ]),
    meter.canvas,
    rulerCanvas,
    el("div", { style: "display:flex; align-items:center; gap:8px; flex-wrap:wrap" }, [
      el("label", { style: "display:flex; align-items:center; gap:6px; font-size:11px; color:var(--muted)" }, [
        "Порог:", threshInput,
      ]),
      threshBadge,
      el("span", { class: "spacer" }),
      calibStatus,
    ]),
    el("div", { class: "dim", style: "font-size:10px; color:var(--muted); line-height:1.3" },
      "Перетащи оранжевую линию или введи число (Enter). " +
      "Полоска: голубой fill = текущий score, оранжевая метка = порог. " +
      "Значок «⚡ АДАМ!» загорается при каждом реальном срабатывании."),
  ]);
  wrapper._dispose = () => {
    rulerDisposed = true;
    if (rulerRAF) cancelAnimationFrame(rulerRAF);
    clearInterval(clockInterval);
    if (typeof unsub === "function") try { unsub(); } catch (_) {}
    try { meter.dispose(); } catch (_) {}
  };
  return wrapper;
}

// ── audioInput.js Card 4: Monitor «слушать микрофон» (D-06, D-07) ────────────
// Raw mono 16-bit LE PCM @ 16000 Hz over WebSocket → Web Audio API playback.

const MONITOR_SAMPLE_RATE = 16000;

function buildMonitorSection(initialTap) {
  const badge = statusBadge();
  const listenBtn = el("button", { class: "btn" }, "▶ Слушать микрофон");
  const tapToggle = el("select", { class: "select", style: "font-size:11px" }, [
    el("option", { value: "post_eq", selected: initialTap !== "pre_eq" ? "selected" : null }, "post-EQ (что слышит модель)"),
    el("option", { value: "pre_eq", selected: initialTap === "pre_eq" ? "selected" : null }, "pre-EQ (сырой вход)"),
  ]);

  let ws = null;
  let audioCtx = null;
  let processor = null;
  let listening = false;
  // Ring of small Float32 chunks consumed by the ScriptProcessor callback —
  // decouples WS message arrival cadence from the audio render cadence.
  let pcmQueue = [];
  let queuedSamples = 0;
  const MAX_QUEUED_SAMPLES = MONITOR_SAMPLE_RATE * 2; // ~2s — backpressure cap

  function int16ToFloat32(buf) {
    const view = new DataView(buf);
    const n = buf.byteLength / 2;
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      out[i] = view.getInt16(i * 2, true) / 32768;
    }
    return out;
  }

  function pullSamples(n) {
    const out = new Float32Array(n);
    let written = 0;
    while (written < n && pcmQueue.length) {
      const chunk = pcmQueue[0];
      const take = Math.min(chunk.length, n - written);
      out.set(chunk.subarray(0, take), written);
      written += take;
      queuedSamples -= take;
      if (take === chunk.length) pcmQueue.shift();
      else pcmQueue[0] = chunk.subarray(take);
    }
    // Remaining = silence (zeros) — avoids clicks on underrun.
    return out;
  }

  function stopListening() {
    listening = false;
    listenBtn.textContent = "▶ Слушать микрофон";
    listenBtn.classList.remove("btn-primary");
    if (ws) { try { ws.close(); } catch (_) {} ws = null; }
    if (processor) { try { processor.disconnect(); } catch (_) {} processor = null; }
    if (audioCtx) { try { audioCtx.close(); } catch (_) {} audioCtx = null; }
    pcmQueue = [];
    queuedSamples = 0;
    badge.textContent = "";
    badge.classList.remove("ok", "warn", "bad");
  }

  function startListening() {
    flashBusy(badge, "подключение…");
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${window.location.host}/api/audio/monitor`);
    ws.binaryType = "arraybuffer";

    const Ctx = window.AudioContext || window.webkitAudioContext;
    audioCtx = new Ctx();
    // ScriptProcessorNode: bufferSize 4096 ≈ 256ms at 16kHz — coarse but fine
    // for a diagnostic monitor; smaller sizes risk underrun on a busy main thread.
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (ev) => {
      const out = ev.outputBuffer.getChannelData(0);
      out.set(pullSamples(out.length));
    };
    processor.connect(audioCtx.destination);

    ws.onopen = () => {
      listening = true;
      listenBtn.textContent = "■ Остановить";
      listenBtn.classList.add("btn-primary");
      flashOk(badge, "стрим идёт");
    };
    ws.onmessage = (ev) => {
      if (!(ev.data instanceof ArrayBuffer) || ev.data.byteLength === 0) return;
      // Web Audio runs at the device's native rate (commonly 44100/48000);
      // the incoming PCM is 16000 Hz mono. AudioContext({sampleRate}) is not
      // universally honoured for ScriptProcessor graphs, so we resample by
      // simple linear interpolation into the queue at push time — cheap and
      // adequate for a monitoring/diagnostic signal (not archival quality).
      const samples16k = int16ToFloat32(ev.data);
      const ratio = audioCtx.sampleRate / MONITOR_SAMPLE_RATE;
      const outLen = Math.round(samples16k.length * ratio);
      const resampled = new Float32Array(outLen);
      for (let i = 0; i < outLen; i++) {
        const srcPos = i / ratio;
        const i0 = Math.floor(srcPos);
        const i1 = Math.min(i0 + 1, samples16k.length - 1);
        const frac = srcPos - i0;
        resampled[i] = samples16k[i0] * (1 - frac) + samples16k[i1] * frac;
      }
      // Backpressure: drop oldest queued audio if the client can't keep up —
      // never let memory grow unbounded (mirrors the server-side ring policy).
      pcmQueue.push(resampled);
      queuedSamples += resampled.length;
      while (queuedSamples > MAX_QUEUED_SAMPLES && pcmQueue.length > 1) {
        queuedSamples -= pcmQueue[0].length;
        pcmQueue.shift();
      }
    };
    ws.onerror = () => {
      flashBad(badge, "ошибка соединения");
    };
    ws.onclose = () => {
      if (listening) {
        toast("Монитор: соединение закрыто", "warn");
      }
      stopListening();
    };
  }

  listenBtn.addEventListener("click", () => {
    if (listening) stopListening();
    else startListening();
  });

  tapToggle.addEventListener("change", async () => {
    flashBusy(badge);
    try {
      await api.raw("/api/tuning", { method: "PUT", body: { audio_input: { dsp: { monitor_tap: tapToggle.value } } } });
      flashOk(badge);
    } catch (e) {
      flashBad(badge);
      toast(`monitor_tap: ${e.message}`, "bad", 5000);
    }
  });

  const wrapper = el("div", { class: "col", style: "gap:8px" }, [
    el("div", { style: "display:flex; align-items:center; gap:10px; flex-wrap:wrap" }, [
      listenBtn,
      el("label", { style: "display:flex; align-items:center; gap:6px; font-size:11px; color:var(--muted)" }, [
        "источник:", tapToggle,
      ]),
      el("span", { class: "spacer" }),
      badge,
    ]),
    el("div", { class: "dim", style: "font-size:10px; color:var(--muted); line-height:1.4" },
      "WebSocket-стрим сырого PCM (16-бит, 16 кГц моно) — ровно то, что слышит модель в режиме post-EQ (WYSIWYG, D-02/D-06). " +
      "Half-duplex mute не затрагивается: это прослушка входа, не TTS-выход. " +
      "Во время TTS поток может быть тихим/прерывистым — это нормально."),
  ]);
  wrapper._dispose = () => stopListening();
  return wrapper;
}

// ── audioInput.js Card 5: Preset CRUD (D-05) ──────────────────────────────────

function buildPresetSection(eqEditor, onActivated) {
  const badge = statusBadge();
  const list = el("div", { class: "col", style: "gap:6px" });
  const nameInput = el("input", { class: "input", type: "text", placeholder: "имя пресета", style: "max-width:220px" });
  const saveBtn = el("button", { class: "btn" }, "💾 Сохранить текущую кривую как пресет");

  let presets = [];
  let activePreset = null;

  async function refresh() {
    try {
      const res = await api.get("/api/audio/presets");
      presets = res.presets || [];
      activePreset = res.active_preset || null;
      render();
    } catch (e) {
      list.innerHTML = "";
      list.appendChild(el("div", { class: "muted bad" }, `Ошибка загрузки пресетов: ${e.message}`));
    }
  }

  function render() {
    list.innerHTML = "";
    if (!presets.length) {
      list.appendChild(el("div", { class: "muted", style: "font-size:11px" }, "Пресетов пока нет — сохрани текущую кривую."));
      return;
    }
    presets.forEach((p) => {
      const isActive = p.name === activePreset;
      const rowBadge = statusBadge();
      const activateBtn = el("button", {
        class: isActive ? "btn" : "btn btn-ghost", style: "font-size:10px; padding:2px 8px",
        disabled: isActive ? "disabled" : null,
        onclick: async () => {
          flashBusy(rowBadge);
          try {
            const res = await api.post(`/api/audio/presets/${encodeURIComponent(p.name)}/activate`);
            if (eqEditor) eqEditor.setCurve({ hpf: res.dsp.hpf, bands: res.dsp.bands });
            if (typeof onActivated === "function") onActivated();
            activePreset = res.active_preset;
            flashOk(rowBadge, "активен");
            render();
          } catch (e) { flashBad(rowBadge); toast(`активация: ${e.message}`, "bad", 5000); }
        },
      }, isActive ? "✓ активен" : "включить");
      const renameBtn = el("button", {
        class: "btn btn-ghost", style: "font-size:10px; padding:2px 8px",
        onclick: async () => {
          const next = prompt("Новое имя пресета:", p.name);
          if (!next || next === p.name) return;
          flashBusy(rowBadge);
          try {
            await api.raw(`/api/audio/presets/${encodeURIComponent(p.name)}`, { method: "PUT", body: { name: next, hpf: p.hpf, bands: p.bands } });
            flashOk(rowBadge, "переименован");
            await refresh();
          } catch (e) { flashBad(rowBadge); toast(`переименование: ${e.message}`, "bad", 5000); }
        },
      }, "✎");
      const updateBtn = el("button", {
        class: "btn btn-ghost", style: "font-size:10px; padding:2px 8px",
        onclick: async () => {
          if (!eqEditor) return;
          if (!confirm(`Перезаписать пресет «${p.name}» текущей кривой EQ?`)) return;
          flashBusy(rowBadge);
          try {
            const curve = { hpf: eqEditor.state.hpf, bands: eqEditor.state.eqBands };
            await api.raw(`/api/audio/presets/${encodeURIComponent(p.name)}`, { method: "PUT", body: { name: p.name, ...curve } });
            flashOk(rowBadge, "обновлён");
            await refresh();
          } catch (e) { flashBad(rowBadge); toast(`обновление: ${e.message}`, "bad", 5000); }
        },
      }, "⤓ записать текущую");
      const deleteBtn = el("button", {
        class: "btn btn-ghost", style: "font-size:10px; padding:2px 8px; color:var(--bad)",
        onclick: async () => {
          if (!confirm(`Удалить пресет «${p.name}»?`)) return;
          flashBusy(rowBadge);
          try {
            await api.del(`/api/audio/presets/${encodeURIComponent(p.name)}`);
            flashOk(rowBadge, "удалён");
            await refresh();
          } catch (e) { flashBad(rowBadge); toast(`удаление: ${e.message}`, "bad", 5000); }
        },
      }, "✕");

      list.appendChild(el("div", {
        style: `display:flex; align-items:center; gap:6px; padding:4px 8px; border-radius:4px; ` +
          `background:${isActive ? "var(--bg-2)" : "transparent"}; border:1px solid ${isActive ? "var(--accent)" : "var(--line)"}`,
      }, [
        el("span", { style: "font-size:12px; font-weight:500; min-width:120px" }, p.name),
        el("span", { class: "dim", style: "font-size:10px; color:var(--muted)" }, `${(p.bands || []).length} полос · HPF ${Math.round(p.hpf?.hz ?? 0)} Гц`),
        el("span", { class: "spacer" }),
        activateBtn, updateBtn, renameBtn, deleteBtn, rowBadge,
      ]));
    });
  }

  saveBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim();
    if (!name) { toast("Укажи имя пресета", "warn"); return; }
    if (!eqEditor) return;
    flashBusy(badge);
    try {
      const curve = { hpf: eqEditor.state.hpf, bands: eqEditor.state.eqBands };
      await api.post("/api/audio/presets", { name, ...curve });
      nameInput.value = "";
      flashOk(badge, "сохранён");
      await refresh();
    } catch (e) {
      flashBad(badge);
      toast(`создание пресета: ${e.message}`, "bad", 5000);
    }
  });

  refresh();

  return el("div", { class: "col", style: "gap:8px" }, [
    el("div", { style: "display:flex; align-items:center; gap:8px; flex-wrap:wrap" }, [
      nameInput, saveBtn, el("span", { class: "spacer" }), badge,
    ]),
    el("div", { class: "dim", style: "font-size:10px; color:var(--muted)" },
      "Пресет = срез HPF + полосы EQ текущей кривой. Хранится в System/Config.json (tuning.audio_input.presets), переживает рестарт."),
    list,
  ]);
}

// ── Main mount ────────────────────────────────────────────────────────────────

export function mount(target) {
  const disposables = [];
  const container = el("div", { class: "col" });
  const refreshBtn = el("button", { class: "btn", onclick: () => renderAll() }, "Перезагрузить");

  target.appendChild(el("section", { class: "col" }, [
    el("div", { class: "row", style: "flex-wrap:wrap; gap:8px" }, [
      el("div", { class: "caps" }, "Аудио и видео · вход/выход, wake-word, видеопоток, сцена"),
      el("span", { class: "spacer" }),
      refreshBtn,
    ]),
    container,
  ]));

  async function renderAll() {
    while (disposables.length) { const fn = disposables.pop(); try { fn(); } catch (_) {} }
    container.innerHTML = "";
    container.appendChild(el("div", { class: "muted" }, [el("span", { class: "spinner" }), " загрузка…"]));

    const [configRes, tuningRes] = await Promise.allSettled([
      api.get("/api/config"),
      api.get("/api/tuning"),
    ]);

    if (configRes.status === "rejected") {
      container.innerHTML = "";
      container.appendChild(el("div", { class: "card" }, el("div", { class: "card-body bad" },
        `Ошибка загрузки конфигурации: ${configRes.reason?.message}`)));
      return;
    }

    const config = configRes.value;
    const tuning = tuningRes.status === "fulfilled" ? tuningRes.value : {};
    const ctx = { renderAll };
    const inputGain = getNested(config, "media.audio.input_gain") || {};
    const audioInput = getNested(tuning, "audio_input") || { dsp: { enabled: true, hpf: { enabled: true, hz: 220 }, bands: [], monitor_tap: "post_eq" } };
    const dsp = audioInput.dsp || { enabled: true, hpf: { enabled: true, hz: 220 }, bands: [], monitor_tap: "post_eq" };

    container.innerHTML = "";
    const cardGrid = el("div", { class: "card-grid" });

    // ── Config-schema cards (Видео / Микрофон и VAD / OWW · Wake word /
    //    Тайминги голосового пайплайна / Воркер описания сцены) ──────────────
    SCHEMA.forEach((group) => {
      const sectionData = getNested(config, group.section) || {};
      const grid = el("div", { class: "field-grid" });

      group.fields.forEach((field) => {
        const value = sectionData[field.key];
        const isWide = field.type === "textarea";

        const row = renderFieldRow(field, value, (f, st) =>
          fieldInput(f, value, (v) => saveConfigField(group.section, field.key, v, st)));
        if (isWide) row.classList.add("field-wide");
        grid.appendChild(row);
      });

      const badge = el("span", { class: "caps mono dim" }, group.section);

      const bodyChildren = [grid];
      if (typeof group.extras === "function") {
        const extra = group.extras(ctx, sectionData);
        if (extra) {
          bodyChildren.push(extra);
          if (typeof extra._dispose === "function") disposables.push(extra._dispose);
        }
      }

      const card = el("section", { class: "card" }, [
        el("div", { class: "card-header" }, [
          el("span", { class: "card-title" }, group.title),
          badge,
        ]),
        el("div", { class: "card-body" }, bodyChildren),
      ]);
      const hasTextarea = group.fields.some((f) => f.type === "textarea");
      if (hasTextarea) card.classList.add("card-full");
      cardGrid.appendChild(card);
    });

    // ── audioInput.js Card 1: Volume (NOT card-full — D-15/WEBUI-R07) ────────
    cardGrid.appendChild(el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Громкость входа"),
        el("span", { class: "caps mono dim" }, "media.audio.input_gain"),
      ]),
      el("div", { class: "card-body" }, buildVolumeSection(inputGain)),
    ]));

    // ── audioInput.js Card 2: Graphic EQ + toggles (card-full) ───────────────
    async function patchDsp(partial) {
      await api.raw("/api/tuning", { method: "PUT", body: { audio_input: { dsp: partial } } });
    }
    const eqWrapper = buildEqSection(dsp, {
      onCurveCommit: (curve) => patchDsp({ hpf: curve.hpf, bands: curve.bands }),
      onMasterToggle: (enabled) => patchDsp({ enabled }),
      onHpfToggle: (_enabled, hpf) => patchDsp({ hpf }),
      onBandToggle: (_idx, _enabled, bands) => patchDsp({ bands }),
      onAddBand: (bands) => patchDsp({ bands }),
      onRemoveBand: (_idx, bands) => patchDsp({ bands }),
    });
    cardGrid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Графический эквалайзер · тумблеры (D-01, D-04)"),
        el("span", { class: "caps mono dim" }, "tuning.audio_input.dsp"),
      ]),
      el("div", { class: "card-body" }, eqWrapper),
    ]));
    if (typeof eqWrapper._dispose === "function") disposables.push(eqWrapper._dispose);

    // ── audioInput.js Card 3: OWW threshold + score (card-full) ─────────────
    const owwWrapper = buildOwwSection();
    cardGrid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Калибровка wake-word «адам» (D-08)"),
        el("span", { class: "caps mono dim" }, "wake_word.threshold"),
      ]),
      el("div", { class: "card-body" }, owwWrapper),
    ]));
    if (typeof owwWrapper._dispose === "function") disposables.push(owwWrapper._dispose);

    // ── audioInput.js Card 4: Monitor (card-full) ─────────────────────────────
    const monitorWrapper = buildMonitorSection(dsp.monitor_tap);
    cardGrid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Слушать микрофон (D-06, D-07)"),
        el("span", { class: "caps mono dim" }, "WS /api/audio/monitor"),
      ]),
      el("div", { class: "card-body" }, monitorWrapper),
    ]));
    if (typeof monitorWrapper._dispose === "function") disposables.push(monitorWrapper._dispose);

    // ── audioInput.js Card 5: Presets (card-full) ──────────────────────────────
    const presetWrapper = buildPresetSection(
      eqWrapper._editor,
      () => { if (eqWrapper._refreshToggles) eqWrapper._refreshToggles(); },
    );
    cardGrid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Пресеты EQ (D-05)"),
        el("span", { class: "caps mono dim" }, "/api/audio/presets"),
      ]),
      el("div", { class: "card-body" }, presetWrapper),
    ]));

    container.appendChild(cardGrid);
    container.appendChild(el("div", { class: "muted", style: "font-size:12px; padding:8px 0" }, [
      el("span", null, "Сырые runtime-параметры → "),
      el("a", { href: "#/tuning", style: "color:var(--accent)" }, "Тюнинг (raw)"),
    ]));
  }

  renderAll();
  return () => {
    while (disposables.length) { const fn = disposables.pop(); try { fn(); } catch (_) {} }
  };
}

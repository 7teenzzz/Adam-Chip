// Phase 31 — «Аудио-вход» panel: operator tuning surface for the microphone
// INPUT path (mic → InputDSP → OWW/ASR). WYSIWYG (D-02): the spectrum, the
// graphic EQ and the monitor all show/play the SAME post-EQ signal the model
// hears.
//
// Sections (plan Tasks 5 & 6):
//   1. Volume   → media.audio.input_gain (D-01 Phase 30, durable hw gain)
//   2. Graphic EQ + per-stage toggles → tuning.audio_input.dsp (D-01,D-04)
//   3. OWW threshold + live score (reuses wakeMeter.js, D-08)
//   4. Monitor «слушать микрофон» → WS /api/audio/monitor + pre/post toggle (D-06,D-07)
//   5. Preset CRUD → /api/audio/presets* (D-05)
//
// Conventions: vanilla JS module, `el()` helper, `api` wrapper, SSE via
// subscribeEvents (owned by sub-widgets). UI strings in Russian, comments in
// English — matches the rest of System/WebUI.

import { api, subscribeEvents } from "../api.js";
import { toast } from "../widgets/toast.js";
import { createWakeMeter, createCalibrateButton } from "../widgets/wakeMeter.js";
import { createEqEditor } from "../widgets/eqEditor.js";

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

// ── Section 1: Volume slider (media.audio.input_gain, D-01 Phase 30) ─────────

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

// ── Section 2: Graphic EQ + toggles (tuning.audio_input.dsp, D-01/D-04) ──────

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

// ── Section 3: OWW threshold + live score (D-08, reuse wakeMeter.js) ────────

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
  // Makes the numeric value legible at a glance (the vertical meter above shows
  // the bar spectogram; the ruler shows the exact score number per frame).
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

// ── Section 4: Monitor «слушать микрофон» (D-06, D-07) ──────────────────────
// Raw mono 16-bit LE PCM @ 16000 Hz over WebSocket → Web Audio API playback.
// Uses ScriptProcessorNode (deprecated but universally supported and trivial
// for this volume — AudioWorklet would need a separate module file served
// statically; ScriptProcessor avoids that complexity for a "лёгкий стрим"
// diagnostic feature that runs for short bursts, not continuously).

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

// ── Section 5: Preset CRUD (D-05) ────────────────────────────────────────────

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
      el("div", { class: "caps" }, "Аудио-вход · mic → DSP → wake-word/ASR (живая настройка, WYSIWYG)"),
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

    if (configRes.status === "rejected" || tuningRes.status === "rejected") {
      container.innerHTML = "";
      container.appendChild(el("div", { class: "card" }, el("div", { class: "card-body bad" },
        `Ошибка загрузки: ${(configRes.reason || tuningRes.reason)?.message}`)));
      return;
    }

    const config = configRes.value;
    const tuning = tuningRes.value;
    const inputGain = getNested(config, "media.audio.input_gain") || {};
    const audioInput = getNested(tuning, "audio_input") || { dsp: { enabled: true, hpf: { enabled: true, hz: 220 }, bands: [], monitor_tap: "post_eq" } };
    const dsp = audioInput.dsp || { enabled: true, hpf: { enabled: true, hz: 220 }, bands: [], monitor_tap: "post_eq" };

    container.innerHTML = "";
    const grid = el("div", { class: "card-grid" });

    // ── Card 1: Volume ─────────────────────────────────────────────────────
    grid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Громкость входа"),
        el("span", { class: "caps mono dim" }, "media.audio.input_gain"),
      ]),
      el("div", { class: "card-body" }, buildVolumeSection(inputGain)),
    ]));

    // ── Card 2: Graphic EQ + toggles ───────────────────────────────────────
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
    grid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Графический эквалайзер · тумблеры (D-01, D-04)"),
        el("span", { class: "caps mono dim" }, "tuning.audio_input.dsp"),
      ]),
      el("div", { class: "card-body" }, eqWrapper),
    ]));
    if (typeof eqWrapper._dispose === "function") disposables.push(eqWrapper._dispose);

    // ── Card 3: OWW threshold + score ──────────────────────────────────────
    const owwWrapper = buildOwwSection();
    grid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Калибровка wake-word «адам» (D-08)"),
        el("span", { class: "caps mono dim" }, "wake_word.threshold"),
      ]),
      el("div", { class: "card-body" }, owwWrapper),
    ]));
    if (typeof owwWrapper._dispose === "function") disposables.push(owwWrapper._dispose);

    // ── Card 4: Monitor ─────────────────────────────────────────────────────
    const monitorWrapper = buildMonitorSection(dsp.monitor_tap);
    grid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Слушать микрофон (D-06, D-07)"),
        el("span", { class: "caps mono dim" }, "WS /api/audio/monitor"),
      ]),
      el("div", { class: "card-body" }, monitorWrapper),
    ]));
    if (typeof monitorWrapper._dispose === "function") disposables.push(monitorWrapper._dispose);

    // ── Card 5: Presets ─────────────────────────────────────────────────────
    const presetWrapper = buildPresetSection(
      eqWrapper._editor,
      () => { if (eqWrapper._refreshToggles) eqWrapper._refreshToggles(); },
    );
    grid.appendChild(el("section", { class: "card card-full" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Пресеты EQ (D-05)"),
        el("span", { class: "caps mono dim" }, "/api/audio/presets"),
      ]),
      el("div", { class: "card-body" }, presetWrapper),
    ]));

    container.appendChild(grid);
    container.appendChild(el("div", { class: "muted", style: "font-size:12px; padding:8px 0" }, [
      el("span", null, "Параметры распознавания и устройства → "),
      el("a", { href: "#/settings", style: "color:var(--accent)" }, "Конфигурация"),
      el("span", null, " · сырые runtime-параметры → "),
      el("a", { href: "#/tuning", style: "color:var(--accent)" }, "Тюнинг (raw)"),
    ]));
  }

  renderAll();
  return () => {
    while (disposables.length) { const fn = disposables.pop(); try { fn(); } catch (_) {} }
  };
}

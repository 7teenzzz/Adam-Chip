// Phase 31 Wave 3 (Task 5/6) — graphic EQ editor for the microphone INPUT path.
//
// Renders a log-frequency spectrum (reusing the same `audio_level` SSE bands[24]
// feed as wakeMeter.js) and overlays DRAGGABLE control points:
//   - one diamond per parametric band (`tuning.audio_input.dsp.bands[i]`):
//       drag   → freq_hz (x, log scale) × gain_db (y)
//       wheel  → q (scroll to widen/narrow)
//   - one vertical dashed line for the HPF cutoff (`dsp.hpf.hz`):
//       drag   → hz (x only)
//
// WYSIWYG (D-02): the spectrum bars are the SAME post-EQ signal the model
// hears (when monitor_tap=post_eq) — operator sees exactly what they hear.
//
// The widget does NOT write to the API directly for every drag tick — it
// calls `onChange(curve)` on pointerup (drag-then-persist-on-release, mirrors
// wakeMeter.js's threshold-line pattern) where `curve = { hpf, bands }`.
// The host panel owns the actual PUT /api/tuning write + debouncing policy.
//
// Disabled stages (enabled=false) render greyed/dimmed (D-04) but remain
// draggable — toggling is a separate UI control owned by the host panel.
//
// Exports createEqEditor(opts) → { canvas, setCurve(curve), dispose() }

import { subscribeEvents } from "../api.js";

const N_BANDS = 24;
const OWW_STRIP_H = 20; // px reserved at canvas bottom for the OWW score overlay

const GREEN = [67, 209, 122];
const YELLOW = [234, 200, 80];
const RED = [220, 80, 80];

// Frequency axis range — mirrors media.audio.spectrum_min_hz/_max_hz defaults.
// Fetched from /api/config at mount; these are fallbacks only.
const DEFAULT_MIN_HZ = 80;
const DEFAULT_MAX_HZ = 8000;

// Gain axis range for band points — matches InputDspBand gain_db bounds (±24 dB).
const GAIN_RANGE_DB = 24;

const BAND_COLOR = "rgba(96,165,250,0.95)";
const BAND_COLOR_DIM = "rgba(120,130,145,0.55)";
const HPF_COLOR = "rgba(234,200,80,0.95)";
const HPF_COLOR_DIM = "rgba(140,135,110,0.55)";

function lerp(a, b, t) { return a + (b - a) * t; }
function rgbBlend(c1, c2, t) { return [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)]; }
function colorForLevel(v, yAt, rAt) {
  let rgb;
  if (v <= yAt) rgb = rgbBlend(GREEN, YELLOW, v / Math.max(0.001, yAt));
  else if (v >= rAt) rgb = RED;
  else rgb = rgbBlend(YELLOW, RED, (v - yAt) / Math.max(0.001, rAt - yAt));
  const a = 0.30 + v * 0.55;
  return `rgba(${rgb[0] | 0},${rgb[1] | 0},${rgb[2] | 0},${a.toFixed(2)})`;
}

// Log-frequency mapping: x in [0,1] ↔ freq in [minHz, maxHz].
function freqToX(freq, minHz, maxHz) {
  const lf = Math.log(Math.max(minHz, Math.min(maxHz, freq)));
  return (lf - Math.log(minHz)) / (Math.log(maxHz) - Math.log(minHz));
}
function xToFreq(x, minHz, maxHz) {
  const lf = Math.log(minHz) + x * (Math.log(maxHz) - Math.log(minHz));
  return Math.exp(lf);
}
// Gain: y in [0,1] ↔ gain in [+GAIN_RANGE, -GAIN_RANGE] (top = boost, bottom = cut).
function gainToY(gainDb) {
  return 0.5 - gainDb / (2 * GAIN_RANGE_DB);
}
function yToGain(y) {
  return (0.5 - y) * 2 * GAIN_RANGE_DB;
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

// ── RBJ biquad frequency response (same formulas as audio_dsp.py) ────────────
// Returns magnitude in dB at the given normalised radian frequency omega = 2πf/Fs.
function _biquadMagDB(b0, b1, b2, a1, a2, omega) {
  const c1 = Math.cos(omega), c2 = Math.cos(2 * omega);
  const s1 = Math.sin(omega), s2 = Math.sin(2 * omega);
  const nr = b0 + b1 * c1 + b2 * c2, ni = -(b1 * s1 + b2 * s2);
  const dr = 1  + a1 * c1 + a2 * c2, di = -(a1 * s1 + a2 * s2);
  const mag2 = (nr * nr + ni * ni) / Math.max(dr * dr + di * di, 1e-30);
  return 10 * Math.log10(Math.max(mag2, 1e-30));
}

// Compute RBJ normalised coefficients (b0,b1,b2,a1,a2) for one filter.
// Returns null if the filter has negligible effect.
function _rbjCoeffs(sr, type, f0, gainDb, q) {
  if (f0 <= 0 || f0 >= sr * 0.5 || q <= 0) return null;
  const w0 = 2 * Math.PI * f0 / sr;
  const cw = Math.cos(w0), sw = Math.sin(w0);
  const alpha = sw / (2 * Math.max(q, 1e-3));
  const A = Math.pow(10, gainDb / 40);
  let b0, b1, b2, a0, a1, a2;
  if (type === "peaking") {
    if (Math.abs(gainDb) < 0.01) return null;
    b0 = 1 + alpha * A; b1 = -2 * cw; b2 = 1 - alpha * A;
    a0 = 1 + alpha / A; a1 = -2 * cw; a2 = 1 - alpha / A;
  } else if (type === "highpass") {
    b0 = (1 + cw) / 2; b1 = -(1 + cw); b2 = (1 + cw) / 2;
    a0 = 1 + alpha;    a1 = -2 * cw;   a2 = 1 - alpha;
  } else if (type === "lowpass") {
    b0 = (1 - cw) / 2; b1 = 1 - cw;   b2 = (1 - cw) / 2;
    a0 = 1 + alpha;    a1 = -2 * cw;   a2 = 1 - alpha;
  } else if (type === "lowshelf") {
    if (Math.abs(gainDb) < 0.01) return null;
    const sa = 2 * Math.sqrt(A) * alpha;
    b0 = A * ((A + 1) - (A - 1) * cw + sa); b1 = 2 * A * ((A - 1) - (A + 1) * cw); b2 = A * ((A + 1) - (A - 1) * cw - sa);
    a0 = (A + 1) + (A - 1) * cw + sa;       a1 = -2 * ((A - 1) + (A + 1) * cw);    a2 = (A + 1) + (A - 1) * cw - sa;
  } else if (type === "highshelf") {
    if (Math.abs(gainDb) < 0.01) return null;
    const sa = 2 * Math.sqrt(A) * alpha;
    b0 = A * ((A + 1) + (A - 1) * cw + sa); b1 = -2 * A * ((A - 1) + (A + 1) * cw); b2 = A * ((A + 1) + (A - 1) * cw - sa);
    a0 = (A + 1) - (A - 1) * cw + sa;       a1 = 2 * ((A - 1) - (A + 1) * cw);      a2 = (A + 1) - (A - 1) * cw - sa;
  } else {
    return null;
  }
  return { b0: b0/a0, b1: b1/a0, b2: b2/a0, a1: a1/a0, a2: a2/a0 };
}

// Compute combined EQ response (dB) at frequency f for the current HPF + bands.
// sr = sample rate (16000). Returns total gain dB.
function _eqResponseDB(state, f, sr) {
  let total = 0;
  // HPF stage
  if (state.hpf && state.hpf.enabled) {
    const c = _rbjCoeffs(sr, "highpass", state.hpf.hz, 0, 0.707);
    if (c) total += _biquadMagDB(c.b0, c.b1, c.b2, c.a1, c.a2, 2 * Math.PI * f / sr);
  }
  // Parametric bands
  for (const band of (state.eqBands || [])) {
    if (!band.enabled) continue;
    const c = _rbjCoeffs(sr, band.type, band.freq_hz, band.gain_db, band.q);
    if (c) total += _biquadMagDB(c.b0, c.b1, c.b2, c.a1, c.a2, 2 * Math.PI * f / sr);
  }
  return total;
}

export function createEqEditor({ height = 180 } = {}) {
  const canvas = document.createElement("canvas");
  canvas.style.cssText =
    `width:100%; height:${height}px; border-radius:4px; display:block; ` +
    `background:var(--bg-2); cursor:default; touch-action:none`;

  const bands    = new Float32Array(N_BANDS); // post-DSP (what the model hears)
  const preBands = new Float32Array(N_BANDS); // pre-DSP (raw mic input)
  const state = {
    minHz: DEFAULT_MIN_HZ,
    maxHz: DEFAULT_MAX_HZ,
    colorYellowAt: 0.6,
    colorRedAt: 0.85,
    pipelineReady: false,
    // Live curve mirror — set via setCurve(), mutated locally while dragging,
    // committed back to the host via onChange on release.
    hpf: { enabled: true, hz: 220 },
    eqBands: /** @type {Array<{enabled:boolean,type:string,freq_hz:number,gain_db:number,q:number}>} */ ([]),
    dragging: /** @type {null | {kind:'band'|'hpf', index:number, pointerId:number}} */ (null),
    owwScore: 0.0,
    owwThreshold: 0.25,
  };

  let onChange = null;
  let onSelect = null;

  fetch("/api/config")
    .then((r) => (r.ok ? r.json() : null))
    .then((cfg) => {
      if (!cfg) return;
      const a = (cfg.media && cfg.media.audio) || {};
      if (typeof a.spectrum_min_hz === "number") state.minHz = a.spectrum_min_hz;
      if (typeof a.spectrum_max_hz === "number") state.maxHz = a.spectrum_max_hz;
      if (typeof a.spectrum_color_yellow_at === "number") state.colorYellowAt = a.spectrum_color_yellow_at;
      if (typeof a.spectrum_color_red_at === "number") state.colorRedAt = a.spectrum_color_red_at;
    })
    .catch(() => {});

  let rafId = null;
  let disposed = false;

  function rectOf() {
    return canvas.getBoundingClientRect();
  }

  function draw() {
    if (disposed) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = rectOf();
    if (rect.width > 0) {
      const cw = Math.round(rect.width * dpr);
      const ch = Math.round(rect.height * dpr);
      if (canvas.width !== cw || canvas.height !== ch) {
        canvas.width = cw;
        canvas.height = ch;
      }
      const ctx = canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = rect.width;
      const h = rect.height;
      // chartH: area used by spectrum bars + EQ curve + handles.
      // Bottom OWW_STRIP_H+1 pixels are reserved for the OWW score overlay.
      const chartH = h - OWW_STRIP_H - 1;
      ctx.clearRect(0, 0, w, h);

      if (!state.pipelineReady) {
        ctx.fillStyle = "rgba(180,180,190,0.55)";
        ctx.font = "12px ui-sans-serif,system-ui,sans-serif";
        ctx.textBaseline = "middle";
        ctx.textAlign = "center";
        ctx.fillText("⌛ Инициализация…", w / 2, h / 2);
        ctx.textAlign = "start";
        rafId = requestAnimationFrame(draw);
        return;
      }

      // Spectrum bars — log-frequency placement.
      // Pre-DSP (raw mic) drawn first as gray/dim background bars,
      // then post-DSP (what the model hears) drawn on top in colour.
      const gap = 2;
      const barW = (w - (N_BANDS - 1) * gap) / N_BANDS;

      // Floor ticks (baseline markers)
      ctx.fillStyle = "rgba(67,209,122,0.08)";
      for (let i = 0; i < N_BANDS; i++) {
        ctx.fillRect(Math.round(i * (barW + gap)), chartH - 2, Math.max(1, Math.round(barW)), 2);
      }

      // Pre-DSP bars: gray, narrower, no colour coding — shows raw input shape
      for (let i = 0; i < N_BANDS; i++) {
        const v = preBands[i];
        if (v < 0.01) continue;
        const bh = v * (chartH - 3);
        ctx.fillStyle = `rgba(140,150,170,${(0.10 + v * 0.18).toFixed(2)})`;
        ctx.fillRect(
          Math.round(i * (barW + gap)) + 1,
          Math.round(chartH - 2 - bh),
          Math.max(1, Math.round(barW) - 2),
          Math.max(1, Math.round(bh)),
        );
      }

      // Post-DSP bars: full colour (what the model hears)
      for (let i = 0; i < N_BANDS; i++) {
        const v = bands[i];
        if (v < 0.01) continue;
        const bh = v * (chartH - 3);
        ctx.fillStyle = colorForLevel(v, state.colorYellowAt, state.colorRedAt);
        ctx.fillRect(
          Math.round(i * (barW + gap)),
          Math.round(chartH - 2 - bh),
          Math.max(1, Math.round(barW)),
          Math.max(1, Math.round(bh)),
        );
      }

      // Zero-gain reference line.
      const yZero = gainToY(0) * chartH;
      ctx.strokeStyle = "rgba(255,255,255,0.10)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, Math.round(yZero) + 0.5);
      ctx.lineTo(w, Math.round(yZero) + 0.5);
      ctx.stroke();

      // EQ frequency response curve — composite of all active filters.
      {
        const SR = 16000;
        const N_CURVE = Math.max(80, Math.round(w));
        const pts = new Float32Array(N_CURVE);
        for (let i = 0; i < N_CURVE; i++) {
          const xNorm = i / (N_CURVE - 1);
          const freq = xToFreq(xNorm, state.minHz, state.maxHz);
          const db = _eqResponseDB(state, freq, SR);
          pts[i] = gainToY(clamp(db, -GAIN_RANGE_DB, GAIN_RANGE_DB)) * chartH;
        }
        const grad = ctx.createLinearGradient(0, 0, 0, chartH);
        grad.addColorStop(0,   "rgba(96,165,250,0.22)");
        grad.addColorStop(0.5, "rgba(96,165,250,0.04)");
        grad.addColorStop(1,   "rgba(96,165,250,0.10)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(0, yZero);
        for (let i = 0; i < N_CURVE; i++) {
          ctx.lineTo(i * w / (N_CURVE - 1), pts[i]);
        }
        ctx.lineTo(w, yZero);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(96,165,250,0.75)";
        ctx.lineWidth = 1.5;
        ctx.lineJoin = "round";
        ctx.beginPath();
        ctx.moveTo(0, pts[0]);
        for (let i = 1; i < N_CURVE; i++) {
          ctx.lineTo(i * w / (N_CURVE - 1), pts[i]);
        }
        ctx.stroke();
      }

      // HPF cutoff — vertical dashed line + draggable handle at the chart bottom.
      {
        const hpf = state.hpf || { enabled: true, hz: 220 };
        const xH = freqToX(hpf.hz, state.minHz, state.maxHz) * w;
        const dim = !hpf.enabled;
        ctx.strokeStyle = dim ? HPF_COLOR_DIM : HPF_COLOR;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(Math.round(xH) + 0.5, 0);
        ctx.lineTo(Math.round(xH) + 0.5, chartH);
        ctx.stroke();
        ctx.setLineDash([]);
        const isDrag = state.dragging && state.dragging.kind === "hpf";
        ctx.fillStyle = isDrag ? "rgba(240,184,74,1.0)" : (dim ? HPF_COLOR_DIM : "rgba(240,184,74,0.92)");
        ctx.beginPath();
        ctx.moveTo(xH, chartH - 12);
        ctx.lineTo(xH - 6, chartH - 2);
        ctx.lineTo(xH + 6, chartH - 2);
        ctx.closePath();
        ctx.fill();
        ctx.font = "10px ui-monospace,monospace";
        ctx.fillStyle = dim ? "rgba(200,190,160,0.5)" : "rgba(240,210,150,0.9)";
        ctx.textAlign = "center";
        ctx.fillText(`HPF ${Math.round(hpf.hz)}Hz`, clamp(xH, 28, w - 28), chartH - 16);
        ctx.textAlign = "start";
      }

      // Parametric band points — diamonds, size encodes Q.
      (state.eqBands || []).forEach((band, i) => {
        const x = freqToX(band.freq_hz, state.minHz, state.maxHz) * w;
        const y = gainToY(band.gain_db) * chartH;
        const dim = !band.enabled;
        const isDrag = state.dragging && state.dragging.kind === "band" && state.dragging.index === i;
        const r = clamp(5 + band.q * 1.2, 5, 14);
        ctx.fillStyle = isDrag ? "rgba(96,165,250,1.0)" : (dim ? BAND_COLOR_DIM : BAND_COLOR);
        ctx.beginPath();
        ctx.moveTo(x, y - r);
        ctx.lineTo(x + r, y);
        ctx.lineTo(x, y + r);
        ctx.lineTo(x - r, y);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.45)";
        ctx.lineWidth = 1;
        ctx.stroke();
        if (isDrag) {
          ctx.font = "10px ui-monospace,monospace";
          ctx.fillStyle = "rgba(220,230,255,0.95)";
          ctx.textAlign = "center";
          const label = `${Math.round(band.freq_hz)}Hz · ${band.gain_db >= 0 ? "+" : ""}${band.gain_db.toFixed(1)}dB · Q${band.q.toFixed(2)}`;
          const ly = y < chartH / 2 ? y + r + 12 : y - r - 6;
          ctx.fillText(label, clamp(x, 50, w - 50), ly);
          ctx.textAlign = "start";
        }
      });

      // ── OWW score strip (bottom OWW_STRIP_H px) ──────────────────────────
      {
        const oy = chartH + 1;          // top of strip
        const oh = h - oy;              // strip height

        // Thin separator
        ctx.fillStyle = "rgba(255,255,255,0.07)";
        ctx.fillRect(0, chartH, w, 1);

        // Strip background
        ctx.fillStyle = "rgba(18,18,30,0.75)";
        ctx.fillRect(0, oy, w, oh);

        // Score fill — cyan, or green when above threshold
        const sx = clamp(state.owwScore, 0, 1) * w;
        if (sx > 0.5) {
          const aboveThresh = state.owwScore >= state.owwThreshold;
          ctx.fillStyle = aboveThresh ? "rgba(80,220,110,0.55)" : "rgba(96,165,250,0.40)";
          ctx.fillRect(0, oy + 1, sx, oh - 2);
        }

        // Threshold tick (orange vertical needle)
        const tx = Math.round(clamp(state.owwThreshold, 0, 1) * w);
        ctx.strokeStyle = "rgba(240,184,74,0.88)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(tx + 0.5, oy);
        ctx.lineTo(tx + 0.5, oy + oh);
        ctx.stroke();

        // Labels
        ctx.font = "9px ui-monospace,monospace";
        ctx.textBaseline = "middle";
        const midY = oy + oh / 2;
        ctx.fillStyle = "rgba(120,130,160,0.75)";
        ctx.textAlign = "left";
        ctx.fillText("oww", 3, midY);
        ctx.fillStyle = "rgba(96,165,250,0.88)";
        ctx.textAlign = "right";
        ctx.fillText(state.owwScore.toFixed(3), w - 3, midY);
        ctx.textBaseline = "alphabetic";
        ctx.textAlign = "start";
      }
    }
    rafId = requestAnimationFrame(draw);
  }
  rafId = requestAnimationFrame(draw);

  // ── Hit-testing ───────────────────────────────────────────────────────────
  function hitTest(ev) {
    const rect = rectOf();
    const px = ev.clientX - rect.left;
    const py = ev.clientY - rect.top;
    const w = rect.width;
    const h = rect.height;
    const chartH = h - OWW_STRIP_H - 1;

    // Bands first (they're visually on top).
    let best = null;
    let bestDist = Infinity;
    (state.eqBands || []).forEach((band, i) => {
      const x = freqToX(band.freq_hz, state.minHz, state.maxHz) * w;
      const y = gainToY(band.gain_db) * chartH;
      const d = Math.hypot(px - x, py - y);
      const r = clamp(5 + band.q * 1.2, 5, 14);
      if (d <= r + 6 && d < bestDist) {
        best = { kind: "band", index: i };
        bestDist = d;
      }
    });
    if (best) return best;

    // HPF handle — within ~10px of the cutoff line, anywhere vertically,
    // OR within the bottom-edge triangle hit area.
    const hpf = state.hpf || { enabled: true, hz: 220 };
    const xH = freqToX(hpf.hz, state.minHz, state.maxHz) * w;
    if (Math.abs(px - xH) <= 10) {
      return { kind: "hpf", index: -1 };
    }
    return null;
  }

  function applyDragMove(ev) {
    const rect = rectOf();
    const w = rect.width;
    const h = rect.height;
    const chartH = h - OWW_STRIP_H - 1;
    const px = clamp(ev.clientX - rect.left, 0, w);
    const py = clamp(ev.clientY - rect.top, 0, chartH); // clamp to chart area only
    const drag = state.dragging;
    if (!drag) return;
    if (drag.kind === "hpf") {
      const freq = clamp(xToFreq(px / w, state.minHz, state.maxHz), 20, 2000);
      state.hpf = { ...state.hpf, hz: Math.round(freq) };
    } else if (drag.kind === "band") {
      const band = state.eqBands[drag.index];
      if (!band) return;
      const freq = clamp(xToFreq(px / w, state.minHz, state.maxHz), 20, Math.min(state.maxHz, 8000));
      const gain = clamp(yToGain(py / chartH), -GAIN_RANGE_DB, GAIN_RANGE_DB);
      state.eqBands[drag.index] = {
        ...band,
        freq_hz: Math.round(freq),
        gain_db: Math.round(gain * 10) / 10,
      };
    }
  }

  function commitChange() {
    if (typeof onChange === "function") {
      onChange({
        hpf: { ...state.hpf },
        bands: state.eqBands.map((b) => ({ ...b })),
      });
    }
  }

  canvas.addEventListener("pointerdown", (ev) => {
    const hit = hitTest(ev);
    if (!hit) return;
    state.dragging = { ...hit, pointerId: ev.pointerId };
    try { canvas.setPointerCapture(ev.pointerId); } catch (_) {}
    if (hit.kind === "band" && typeof onSelect === "function") onSelect(hit.index);
    ev.preventDefault();
  });
  canvas.addEventListener("pointermove", (ev) => {
    if (!state.dragging || state.dragging.pointerId !== ev.pointerId) {
      // Hover cursor feedback.
      canvas.style.cursor = hitTest(ev) ? "grab" : "default";
      return;
    }
    canvas.style.cursor = "grabbing";
    applyDragMove(ev);
  });
  const endDrag = (ev) => {
    if (!state.dragging || state.dragging.pointerId !== ev.pointerId) return;
    state.dragging = null;
    canvas.style.cursor = "default";
    try { canvas.releasePointerCapture(ev.pointerId); } catch (_) {}
    commitChange();
  };
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);

  // Wheel over a band point → adjust Q (D-Claude's-discretion: "Q колесом").
  canvas.addEventListener("wheel", (ev) => {
    const hit = hitTest(ev);
    if (!hit || hit.kind !== "band") return;
    ev.preventDefault();
    const band = state.eqBands[hit.index];
    if (!band) return;
    const delta = ev.deltaY > 0 ? -0.1 : 0.1;
    const q = clamp(Math.round((band.q + delta) * 100) / 100, 0.1, 10.0);
    state.eqBands[hit.index] = { ...band, q };
    commitChange();
  }, { passive: false });

  const unsub = subscribeEvents((ev) => {
    if (ev.type === "audio_level_eq") {
      // Primary spectrum source for the EQ canvas: post-DSP bands + pre-DSP background.
      const p = ev.payload || {};
      if (Array.isArray(p.bands) && p.bands.length === N_BANDS) {
        for (let i = 0; i < N_BANDS; i++) bands[i] = +p.bands[i] || 0;
      }
      if (Array.isArray(p.pre_bands) && p.pre_bands.length === N_BANDS) {
        for (let i = 0; i < N_BANDS; i++) preBands[i] = +p.pre_bands[i] || 0;
      }
      if (typeof p.oww_score === "number") state.owwScore = p.oww_score;
      if (typeof p.oww_threshold === "number") state.owwThreshold = p.oww_threshold;
    } else if (ev.type === "oww_score") {
      // Also update oww state from the dedicated oww_score events (fire even when
      // audio_level_eq is throttled) so the strip stays responsive in standby.
      const p = ev.payload || {};
      if (typeof p.score === "number") state.owwScore = p.score;
      if (typeof p.threshold === "number") state.owwThreshold = p.threshold;
    } else if (ev.type === "audio_level") {
      // Keep for pipelineReady state updates only — spectrum is fed via audio_level_eq.
      const vs = (ev.payload || {}).state;
      if (vs === "standby" || vs === "listening" || vs === "reply") state.pipelineReady = true;
      else if (vs === "boot_warmup") state.pipelineReady = false;
    } else if (ev.type === "voice_state_change") {
      const to = ev.payload && ev.payload.to;
      if (to === "standby" || to === "listening" || to === "reply") state.pipelineReady = true;
      else if (to === "boot_warmup") state.pipelineReady = false;
    } else if (ev.type === "voice_loop_stopped") {
      state.pipelineReady = false;
      bands.fill(0);
      preBands.fill(0);
      state.owwScore = 0;
    }
  }, () => {});

  function setCurve(curve, { silent = true } = {}) {
    if (!curve) return;
    if (curve.hpf) state.hpf = { enabled: curve.hpf.enabled !== false, hz: curve.hpf.hz ?? 220 };
    if (Array.isArray(curve.bands)) {
      state.eqBands = curve.bands.map((b) => ({
        enabled: b.enabled !== false,
        type: b.type || "peaking",
        freq_hz: b.freq_hz ?? 1000,
        gain_db: b.gain_db ?? 0,
        q: b.q ?? 1.0,
      }));
    }
    if (!silent) commitChange();
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (typeof unsub === "function") {
      try { unsub(); } catch (_) {}
    }
  }

  return {
    canvas,
    state,
    setCurve,
    dispose,
    set onChange(fn) { onChange = fn; },
    get onChange() { return onChange; },
    set onSelect(fn) { onSelect = fn; },
    get onSelect() { return onSelect; },
  };
}

// Wake-word meter widget.
//
// Renders three layers on one canvas:
//   1. Live audio_level bars (driven by SSE).
//   2. Current OWW score marker (cyan line, decays).
//   3. Threshold line (dashed orange) + slider handle when draggable.
//
// Modes:
//   draggable=false → read-only visualisation (chat panel).
//   draggable=true  → operator can drag the orange line to tune threshold,
//                     PATCHes /api/wake_word/sensitivity on release.
//
// Exports a single factory createWakeMeter(opts) that returns:
//   { canvas, handleEvent(ev), dispose() }
// The host panel is responsible for piping its SSE events into handleEvent.

import { subscribeEvents } from "../api.js";

const BAR_N = 28;

const EQ_SHAPE = Float32Array.from({ length: BAR_N }, (_, i) => {
  const x = i / (BAR_N - 1);
  const peak = Math.exp(-((x - 0.28) ** 2) / 0.06);
  const low = Math.exp(-((x - 0.0) ** 2) / 0.015) * 0.4;
  return Math.max(0.06, Math.min(1.0, peak + low));
});

function thresholdFromEvent(canvas, ev) {
  const rect = canvas.getBoundingClientRect();
  const y = ev.clientY - rect.top;
  const v = 1 - y / Math.max(1, rect.height);
  return Math.max(0.05, Math.min(0.95, v));
}

export function createWakeMeter({ draggable = false, height = 96 } = {}) {
  const canvas = document.createElement("canvas");
  canvas.style.cssText =
    `width:100%; height:${height}px; border-radius:4px; display:block; ` +
    `background:var(--bg-2); ${draggable ? "cursor:ns-resize;" : ""} touch-action:none`;

  const peaks = new Float32Array(BAR_N);
  const state = {
    audioLevel: 0,
    threshold: 0.25,
    score: 0,
    scoreDecay: 0,
    scorePeak: 0,
    scorePeakTs: 0,
    dragging: false,
    engineReady: false,
  };

  // Initial load + listen for external updates (e.g. settings page changes
  // threshold while chat page is open).
  fetch("/api/wake_word/sensitivity")
    .then((r) => r.json())
    .then((d) => {
      if (d && d.ok && typeof d.threshold === "number") {
        state.threshold = d.threshold;
        state.engineReady = true;
      }
    })
    .catch(() => {});

  async function pushThreshold(v, { persist }) {
    if (!state.engineReady) return;
    try {
      await fetch("/api/wake_word/sensitivity", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threshold: v, persist: !!persist }),
      });
    } catch (_) {}
  }

  let rafId = null;

  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
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
      ctx.clearRect(0, 0, w, h);

      const gap = 2;
      const barW = (w - (BAR_N - 1) * gap) / BAR_N;
      const t = Date.now() * 0.0015;
      const displayLevel = Math.min(1.0, state.audioLevel * 4.0);
      for (let i = 0; i < BAR_N; i++) {
        const wobble = 1 + 0.12 * Math.sin(t + i * 0.85);
        const target = displayLevel * EQ_SHAPE[i] * wobble;
        peaks[i] = Math.max(target, peaks[i] * 0.87);
      }

      ctx.fillStyle = "rgba(67,209,122,0.10)";
      for (let i = 0; i < BAR_N; i++) {
        ctx.fillRect(Math.round(i * (barW + gap)), h - 2, Math.max(1, Math.round(barW)), 2);
      }
      for (let i = 0; i < BAR_N; i++) {
        const v = peaks[i];
        if (v < 0.008) continue;
        const bh = v * (h - 3);
        ctx.fillStyle = `rgba(67,209,122,${0.35 + v * 0.65})`;
        ctx.fillRect(
          Math.round(i * (barW + gap)),
          Math.round(h - 2 - bh),
          Math.max(1, Math.round(barW)),
          Math.max(1, Math.round(bh)),
        );
      }

      // Score marker — decay smoothing + peak hold.
      state.scoreDecay = Math.max(state.score, state.scoreDecay * 0.86);
      const now = Date.now();
      if (state.score > state.scorePeak || now - state.scorePeakTs > 1500) {
        state.scorePeak = state.score;
        state.scorePeakTs = now;
      }
      if (state.scoreDecay > 0.02) {
        const yS = (1 - state.scoreDecay) * h;
        ctx.fillStyle = "rgba(96,165,250,0.85)";
        ctx.fillRect(0, Math.round(yS) - 1, w, 2);
      }

      // Threshold line — glows when score is near.
      const yT = (1 - state.threshold) * h;
      const proximity = Math.max(0, Math.min(1, 1 - Math.abs(state.scoreDecay - state.threshold) * 4));
      const alpha = 0.55 + proximity * 0.40;
      ctx.strokeStyle = state.dragging
        ? "rgba(240,184,74,1.0)"
        : `rgba(240,184,74,${alpha.toFixed(2)})`;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(0, Math.round(yT));
      ctx.lineTo(w, Math.round(yT));
      ctx.stroke();
      ctx.setLineDash([]);

      // Handle — only when draggable.
      if (draggable) {
        const knobR = 7;
        ctx.fillStyle = state.dragging ? "rgba(240,184,74,1.0)" : "rgba(240,184,74,0.92)";
        ctx.beginPath();
        ctx.arc(w - knobR - 3, yT, knobR, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(0,0,0,0.45)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      ctx.fillStyle = "rgba(220,220,220,0.78)";
      ctx.font = "10px ui-monospace,monospace";
      ctx.textBaseline = "top";
      ctx.fillText(
        `t=${state.threshold.toFixed(2)}  s=${state.scoreDecay.toFixed(2)}  max=${state.scorePeak.toFixed(2)}`,
        4,
        3,
      );
    }
    rafId = requestAnimationFrame(draw);
  }
  rafId = requestAnimationFrame(draw);

  // Drag-to-tune — only wired up in draggable mode.
  if (draggable) {
    canvas.addEventListener("pointerdown", (ev) => {
      if (!state.engineReady) return;
      state.dragging = true;
      canvas.setPointerCapture(ev.pointerId);
      const v = thresholdFromEvent(canvas, ev);
      state.threshold = v;
      pushThreshold(v, { persist: false });
    });
    canvas.addEventListener("pointermove", (ev) => {
      if (!state.dragging) return;
      const v = thresholdFromEvent(canvas, ev);
      state.threshold = v;
      pushThreshold(v, { persist: false });
    });
    const endDrag = (ev) => {
      if (!state.dragging) return;
      state.dragging = false;
      try { canvas.releasePointerCapture(ev.pointerId); } catch (_) {}
      pushThreshold(state.threshold, { persist: true });
    };
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);
  }

  // The widget owns its own SSE subscription so it works on any panel
  // without the host plumbing events through. Each subscriber is independent
  // (subscribeEvents is just an EventSource wrapper).
  const unsub = subscribeEvents((ev) => {
    if (ev.type === "audio_level") {
      const lvl = ev.payload && ev.payload.level;
      state.audioLevel = typeof lvl === "number" ? lvl : 0;
    } else if (ev.type === "oww_score") {
      const p = ev.payload || {};
      if (typeof p.score === "number") state.score = p.score;
      if (!state.dragging && typeof p.threshold === "number") {
        state.threshold = p.threshold;
        state.engineReady = true;
      }
    } else if (ev.type === "wake_sensitivity_updated") {
      const p = ev.payload || {};
      if (!state.dragging && typeof p.threshold === "number") {
        state.threshold = p.threshold;
      }
    }
  }, () => {});

  function dispose() {
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (typeof unsub === "function") unsub();
  }

  return { canvas, dispose, state };
}

// Calibration button — shared across panels for consistent look + behaviour.
// onComplete(threshold) is called when the operator accepts the recommendation.
export function createCalibrateButton({ onComplete, label = "Калибровать", icon = "⚙" } = {}) {
  let busy = false;
  const status = document.createElement("span");
  status.className = "dim";
  status.style.cssText = "font-size:10px; color:var(--muted)";

  const btn = document.createElement("button");
  btn.className = "btn btn-ghost";
  btn.style.cssText = "font-size:11px; padding:4px 10px";
  btn.textContent = `${icon} ${label}`;
  btn.addEventListener("click", run);

  async function run() {
    if (busy) return;
    if (!confirm(
      "Калибровка фонового шума.\n\n" +
      "Адам послушает комнату 20 секунд.\n" +
      "Не говорите и не двигайте микрофон.\n" +
      "Оставьте обычный фон комнаты (вентилятор, проектор, гул).\n\n" +
      "Продолжить?"
    )) return;
    busy = true;
    btn.disabled = true;
    status.textContent = "Запись шума…";
    status.style.color = "var(--warn)";
    try {
      const resp = await fetch("/api/wake_word/calibrate/noise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration_sec: 20, margin: 0.08 }),
      });
      if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
      const data = await resp.json();
      const rec = data.recommended_threshold;
      const p = data.profile || {};
      const apply = confirm(
        `Профиль шума (${data.duration_sec}с, ${data.samples} событий):\n` +
        `  max  = ${(p.max ?? 0).toFixed(3)}\n` +
        `  p99  = ${(p.p99 ?? 0).toFixed(3)}\n` +
        `  p95  = ${(p.p95 ?? 0).toFixed(3)}\n` +
        `  mean = ${(p.mean ?? 0).toFixed(3)}\n\n` +
        `Рекомендуемый порог: ${rec.toFixed(2)}` +
        (data.warning ? `\n\n⚠ ${data.warning}` : "") +
        `\n\nПрименить?`
      );
      if (apply) {
        await fetch("/api/wake_word/sensitivity", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ threshold: rec, persist: true }),
        });
        status.textContent = `Порог обновлён: ${rec.toFixed(2)}`;
        status.style.color = "var(--accent)";
        if (typeof onComplete === "function") onComplete(rec);
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
      setTimeout(() => { status.textContent = ""; }, 6000);
    }
  }

  return { btn, status };
}

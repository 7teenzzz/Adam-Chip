import { api } from "../api.js";
import { state } from "../state.js";
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

function fmtMs(value) {
  if (value == null) return null;
  if (value >= 1000) return `${(value / 1000).toFixed(2)}с`;
  return `${Math.round(value)}мс`;
}

function bubble(turn) {
  const isAdam = turn.speaker === "adam";
  const wrap = el("div", {
    class: "fade-in",
    style: `display:flex; flex-direction:column; max-width:90%; ${isAdam ? "align-self:flex-start" : "align-self:flex-end"}; gap:4px`,
  });
  const meta = el("div", {
    class: "caps",
    style: `color:${isAdam ? "var(--accent)" : "var(--muted)"}; font-size:10px`,
  }, isAdam ? "АДАМ" : "ЗРИТЕЛЬ");
  const body = el("div", {
    style: `padding:8px 12px; border-radius:var(--radius-m); border:1px solid ${
      isAdam ? "rgba(67,209,122,0.35)" : "var(--line)"
    }; background:${isAdam ? "rgba(67,209,122,0.05)" : "var(--bg-2)"}; white-space:pre-wrap; word-break:break-word; font-size:13px`,
  }, turn.text);

  const footerParts = [];
  footerParts.push(el("span", { class: "dim" }, (turn.ts || "").slice(11, 19)));
  if (turn.timings) {
    const t = turn.timings;
    const tags = [];
    if (t.asr_ms != null) tags.push(`ASR ${fmtMs(t.asr_ms)}`);
    if (t.llm_ms != null) tags.push(`LLM ${fmtMs(t.llm_ms)}`);
    if (t.tts_ms != null) tags.push(`TTS ${fmtMs(t.tts_ms)}`);
    if (t.total_ms != null) tags.push(`∑ ${fmtMs(t.total_ms)}`);
    tags.forEach((tag) => {
      footerParts.push(el("span", { style: "color:var(--accent); opacity:0.7" }, tag));
    });
  }
  if (turn.voice_degraded) {
    footerParts.push(el("span", { style: "color:var(--warn)" }, "голос ↓"));
  }
  const footer = el("div", {
    style: "display:flex; gap:8px; flex-wrap:wrap; font-size:10px; font-family:var(--font-mono)",
  }, footerParts);

  wrap.appendChild(meta);
  wrap.appendChild(body);
  wrap.appendChild(footer);
  return wrap;
}

export function mount(target) {
  // ---- Vision (right panel) ----
  const jetImg = el("img", {
    alt: "Jetson snapshot",
    style: "width:100%; max-height:240px; object-fit:contain; border-radius:var(--radius-s); border:1px solid var(--line); background:var(--bg-2); display:block",
  });
  const jetStatus = el("span", { style: "font-size:10px; color:var(--muted); font-family:var(--font-mono)" }, "—");
  const sceneCaption = el("div", { style: "color:var(--muted); font-size:12px; white-space:pre-wrap; line-height:1.5" }, "Сцена не описана.");

  // ---- Equalizer + Wake-word threshold overlay ----
  // Renders three layers on a single canvas:
  //   1. Live audio_level bars (existing) — what Adam hears.
  //   2. Current OWW score marker (cyan line) — where "адам" lands right now.
  //   3. Threshold slider (orange dashed line + handle) — draggable to tune
  //      OWW sensitivity. PATCHes /api/wake_word/sensitivity on release.
  const eqCanvas = el("canvas", {
    style: "width:100%; height:96px; border-radius:4px; display:block; background:var(--bg-2); cursor:ns-resize; touch-action:none",
  });
  const BAR_N = 28;
  const eqPeaks = new Float32Array(BAR_N);
  let eqServerLevel = 0;   // latest normalized level (0–1) from audio_level SSE event
  let eqRafId = null;

  // Wake-word state (driven by SSE oww_score events + REST GET on mount).
  let wakeThreshold = 0.25;
  let wakeScore = 0;
  let wakeScoreDecay = 0;     // visual smoothing of score marker
  let wakeScorePeak = 0;      // peak hold for short window
  let wakeScorePeakTs = 0;
  let wakeDragging = false;
  let wakePendingPersistTimer = null;
  let wakeEngineReady = false;

  async function loadWakeSensitivity() {
    try {
      const r = await fetch("/api/wake_word/sensitivity");
      const d = await r.json();
      if (d.ok && typeof d.threshold === "number") {
        wakeThreshold = d.threshold;
        wakeEngineReady = true;
      }
    } catch (_) { /* engine not up yet — keep default */ }
  }
  loadWakeSensitivity();

  async function pushWakeThreshold(v, opts = {}) {
    if (!wakeEngineReady) return;
    try {
      await fetch("/api/wake_word/sensitivity", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threshold: v, persist: !!opts.persist }),
      });
    } catch (e) {
      toast?.("Не удалось обновить порог OWW: " + e.message);
    }
  }

  // Spectral shape: voice-like curve peaking around bar 6-10 (mid-low frequencies).
  const EQ_SHAPE = Float32Array.from({ length: BAR_N }, (_, i) => {
    const x = i / (BAR_N - 1);
    const peak = Math.exp(-((x - 0.28) ** 2) / 0.06);        // main voice peak ~1kHz
    const low  = Math.exp(-((x - 0.0)  ** 2) / 0.015) * 0.4; // sub-bass presence
    return Math.max(0.06, Math.min(1.0, peak + low));
  });

  function drawEqualizer() {
    const dpr = window.devicePixelRatio || 1;
    const rect = eqCanvas.getBoundingClientRect();
    if (rect.width > 0) {
      const cw = Math.round(rect.width * dpr), ch = Math.round(rect.height * dpr);
      if (eqCanvas.width !== cw || eqCanvas.height !== ch) {
        eqCanvas.width = cw;
        eqCanvas.height = ch;
      }
      const ctx = eqCanvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = rect.width, h = rect.height;
      ctx.clearRect(0, 0, w, h);

      const gap = 2;
      const barW = (w - (BAR_N - 1) * gap) / BAR_N;
      const t = Date.now() * 0.0015; // slow wobble clock

      // Update peaks with spectral shaping + per-bar organic wobble.
      const displayLevel = Math.min(1.0, eqServerLevel * 4.0); // boost idle signal for visibility
      for (let i = 0; i < BAR_N; i++) {
        const wobble = 1 + 0.12 * Math.sin(t + i * 0.85);
        const target = displayLevel * EQ_SHAPE[i] * wobble;
        eqPeaks[i] = Math.max(target, eqPeaks[i] * 0.87);
      }

      // Dim baseline — always rendered so canvas looks active.
      ctx.fillStyle = "rgba(67,209,122,0.10)";
      for (let i = 0; i < BAR_N; i++) {
        ctx.fillRect(Math.round(i * (barW + gap)), h - 2, Math.max(1, Math.round(barW)), 2);
      }

      // Active bars.
      for (let i = 0; i < BAR_N; i++) {
        const v = eqPeaks[i];
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

      // ── Wake-word overlay ──────────────────────────────────────────────
      // Score marker (cyan line) — pulses on speech, decays back.
      wakeScoreDecay = Math.max(wakeScore, wakeScoreDecay * 0.86);
      const now = Date.now();
      if (wakeScore > wakeScorePeak || now - wakeScorePeakTs > 1500) {
        wakeScorePeak = wakeScore;
        wakeScorePeakTs = now;
      }
      if (wakeScoreDecay > 0.02) {
        const yS = (1 - wakeScoreDecay) * h;
        ctx.fillStyle = "rgba(96,165,250,0.85)";  // cyan-ish (matches "thinking" hearing color family)
        ctx.fillRect(0, Math.round(yS) - 1, w, 2);
      }

      // Threshold line — dashed horizontal. Orange/warn so it stands apart from
      // the green bars. Glows brighter as wakeScore approaches/exceeds it.
      const yT = (1 - wakeThreshold) * h;
      const proximity = Math.max(0, Math.min(1, 1 - Math.abs(wakeScoreDecay - wakeThreshold) * 4));
      const alpha = 0.55 + proximity * 0.40;
      ctx.strokeStyle = wakeDragging
        ? "rgba(240,184,74,1.0)"
        : `rgba(240,184,74,${alpha.toFixed(2)})`;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(0, Math.round(yT));
      ctx.lineTo(w, Math.round(yT));
      ctx.stroke();
      ctx.setLineDash([]);

      // Slider handle — right-side knob on the threshold line.
      const knobR = 7;
      ctx.fillStyle = wakeDragging ? "rgba(240,184,74,1.0)" : "rgba(240,184,74,0.92)";
      ctx.beginPath();
      ctx.arc(w - knobR - 3, yT, knobR, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.45)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Numeric labels — top-left corner, small monospace.
      ctx.fillStyle = "rgba(220,220,220,0.78)";
      ctx.font = "10px ui-monospace,monospace";
      ctx.textBaseline = "top";
      ctx.fillText(
        `t=${wakeThreshold.toFixed(2)}  s=${wakeScoreDecay.toFixed(2)}  max=${wakeScorePeak.toFixed(2)}`,
        4,
        3,
      );
    }
    eqRafId = requestAnimationFrame(drawEqualizer);
  }
  eqRafId = requestAnimationFrame(drawEqualizer);

  // ── Pointer interaction for the threshold slider ───────────────────────
  function thresholdFromEvent(ev) {
    const rect = eqCanvas.getBoundingClientRect();
    const y = ev.clientY - rect.top;
    const v = 1 - (y / Math.max(1, rect.height));
    return Math.max(0.05, Math.min(0.95, v));
  }
  function applyThresholdLive(v) {
    wakeThreshold = v;
    // Live PATCH without persist so the engine updates immediately, but the
    // Config.json write is deferred to pointerup to avoid disk churn on drag.
    pushWakeThreshold(v, { persist: false });
  }
  eqCanvas.addEventListener("pointerdown", (ev) => {
    if (!wakeEngineReady) return;
    wakeDragging = true;
    eqCanvas.setPointerCapture(ev.pointerId);
    applyThresholdLive(thresholdFromEvent(ev));
  });
  eqCanvas.addEventListener("pointermove", (ev) => {
    if (!wakeDragging) return;
    if (wakePendingPersistTimer) { clearTimeout(wakePendingPersistTimer); wakePendingPersistTimer = null; }
    applyThresholdLive(thresholdFromEvent(ev));
  });
  function endDrag(ev) {
    if (!wakeDragging) return;
    wakeDragging = false;
    try { eqCanvas.releasePointerCapture(ev.pointerId); } catch (_) {}
    // One final persist so the chosen value survives a restart.
    pushWakeThreshold(wakeThreshold, { persist: true });
  }
  eqCanvas.addEventListener("pointerup", endDrag);
  eqCanvas.addEventListener("pointercancel", endDrag);

  // ---- Hearing (OWW + ASR) live display ----
  const HEARING_COLORS = {
    loading:      "var(--warn)",   // yellow  — OWW/ASR not ready
    standby:      "var(--accent)", // green   — waiting for wake word
    listening:    "#a855f7",       // purple  — recording / accumulating speech
    reply:        "#a855f7",       // purple  — reply window open (same as listening)
    transcribing: "#f0b84a",       // amber   — WhisperX processing
    thinking:     "#22d3ee",       // cyan    — LLM generating
    tts:          "#60a5fa",       // blue    — Adam is speaking
  };
  const HEARING_LABELS = {
    loading:      "🎧 Инициализация",
    standby:      "🎧 Ожидаю обращения",
    listening:    "🎤 Слушаю",
    reply:        "🎤 Слушаю",
    transcribing: "⏳ Распознаю",
    thinking:     "💭 Думаю",
    tts:          "🔊 Говорю",
  };
  let hearingState = "loading";
  let dotsTick = 0;
  const DOTS_PERIOD_MS = 400;
  const hearingDot = el("span", {
    style: `display:inline-block; width:8px; height:8px; border-radius:50%;
            background:${HEARING_COLORS.loading}; flex-shrink:0; transition:background 0.35s`,
  });
  const asrBox = el("div", {
    style: "min-height:28px; padding:6px 8px; border-radius:4px; background:var(--bg-2); font-size:12px; color:var(--muted); font-family:var(--font-mono); white-space:pre-wrap; word-break:break-word; line-height:1.4",
  }, HEARING_LABELS.loading);

  function renderHearing() {
    asrBox.textContent = (HEARING_LABELS[hearingState] || "—") + ".".repeat(dotsTick);
  }
  function tickDots() {
    dotsTick = (dotsTick + 1) % 4;   // 0,1,2,3 → "" "." ".." "..."
    renderHearing();
  }
  const dotsTimer = setInterval(tickDots, DOTS_PERIOD_MS);

  function updateHearing(newState) {
    hearingState = newState;
    hearingDot.style.background = HEARING_COLORS[newState] || "var(--muted)";
    asrBox.style.color = newState === "loading" ? "var(--muted)" : "var(--text)";
    dotsTick = 0;
    renderHearing();
  }

  // Route to idle: standby if voice loop is up, loading otherwise.
  // Called explicitly when an active SSE state ends.
  function routeToIdle() {
    const running = state.get("status")?.voice_loop?.running;
    updateHearing(running ? "standby" : "loading");
  }

  // Polling-time sync — preserves active SSE-driven states so polling
  // never overrides "слушаю / распознаю / думаю / говорю" mid-flow.
  function syncHearingFromStatus() {
    if (["listening", "reply", "transcribing", "thinking", "tts"].includes(hearingState)) return;
    routeToIdle();
  }
  syncHearingFromStatus();
  state.subscribe("status", syncHearingFromStatus);

  let jetTimer = null, jetInflight = false;

  function refreshSnapshot() {
    if (jetInflight) return;
    jetInflight = true;
    const url = "/api/camera/snapshot.jpg?_=" + Date.now();
    const probe = new Image();
    probe.onload = () => {
      jetImg.src = probe.src;
      jetStatus.textContent = new Date().toLocaleTimeString("ru");
      jetStatus.style.color = "var(--accent)";
      jetInflight = false;
    };
    probe.onerror = () => {
      jetStatus.textContent = "камера недоступна";
      jetStatus.style.color = "var(--bad)";
      jetInflight = false;
      stopJetTimer();
    };
    probe.src = url;
  }

  function startJetTimer() {
    if (!jetTimer) { refreshSnapshot(); jetTimer = setInterval(refreshSnapshot, 1500); }
  }
  function stopJetTimer() {
    if (jetTimer) { clearInterval(jetTimer); jetTimer = null; }
  }

  function paintScene() {
    const sc = state.get("status")?.scene_cache;
    if (!sc?.text) { sceneCaption.textContent = "Сцена не описана."; return; }
    sceneCaption.textContent = sc.text + (sc.stale ? " (устарело)" : "");
  }
  const unsubScene = state.subscribe("status", () => { paintScene(); });
  paintScene();
  startJetTimer();

  // ---- Transcript ----
  const transcript = el("div", {
    id: "chat-transcript",
    style: "flex:1; min-height:0; overflow-y:auto; display:flex; flex-direction:column; gap:12px; padding:4px 2px",
  });

  // ---- Text input ----
  const input = el("textarea", {
    class: "textarea",
    id: "chat-input",
    placeholder: "Скажи что-нибудь Адаму…",
    rows: 2,
    style: "min-height:52px; resize:none",
    onkeydown: (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); send(); }
    },
  });

  const sendBtn = el("button", { class: "btn btn-primary", onclick: () => send() }, "Отправить ⏎");
  const clearBtn = el("button", { class: "btn btn-ghost", onclick: () => { input.value = ""; input.focus(); } }, "Очистить");

  // ---- Wake-word noise calibration UI ----
  // The "Откалибровать" button records 20s of room noise via the orchestrator,
  // computes a recommended threshold above the noise floor, and offers Apply.
  let calibrationInProgress = false;
  const calibStatus = el("span", { class: "dim", style: "font-size:10px; color:var(--muted)" }, "");
  const calibrateBtn = el("button", {
    class: "btn btn-ghost",
    style: "font-size:11px; padding:4px 10px",
    onclick: () => startNoiseCalibration(),
  }, "🎚 Откалибровать по шуму");

  async function startNoiseCalibration() {
    if (calibrationInProgress) return;
    if (!confirm(
      "Калибровка фонового шума.\n\n" +
      "Адам послушает комнату 20 секунд.\n" +
      "Не говорите и не двигайте микрофон.\n" +
      "Оставьте обычный фон комнаты (вентилятор, проектор, гул).\n\n" +
      "Продолжить?"
    )) return;
    calibrationInProgress = true;
    calibrateBtn.disabled = true;
    calibStatus.textContent = "Запись шума…";
    calibStatus.style.color = "var(--warn)";
    try {
      const resp = await fetch("/api/wake_word/calibrate/noise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration_sec: 20, margin: 0.08 }),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(resp.status + " " + detail);
      }
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
        await pushWakeThreshold(rec, { persist: true });
        wakeThreshold = rec;
        calibStatus.textContent = `Порог обновлён: ${rec.toFixed(2)}`;
        calibStatus.style.color = "var(--accent)";
      } else {
        calibStatus.textContent = "Отменено.";
        calibStatus.style.color = "var(--muted)";
      }
    } catch (e) {
      calibStatus.textContent = "Ошибка: " + (e.message || e);
      calibStatus.style.color = "var(--bad)";
    } finally {
      calibrationInProgress = false;
      calibrateBtn.disabled = false;
      setTimeout(() => { calibStatus.textContent = ""; }, 6000);
    }
  }

  // ---- Layout ----
  const card = el("section", { class: "card", style: "flex:1; display:flex; flex-direction:column; min-height:0" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Диалог"),
      el("span", { class: "spacer" }),
      el("span", { class: "caps", id: "chat-state", style: "font-size:11px" }, "—"),
    ]),
    el("div", { class: "card-body", style: "flex:1; display:grid; grid-template-columns:minmax(0,3fr) minmax(0,2fr); gap:0; min-height:0; padding:0" }, [
      // Left: chat
      el("div", { style: "display:flex; flex-direction:column; gap:8px; min-height:0; padding:12px; border-right:1px solid var(--line)" }, [
        transcript,
        el("div", { class: "row-stretch", style: "gap:8px" }, [input]),
        el("div", { class: "row", style: "gap:6px; align-items:center; flex-wrap:wrap" }, [
          sendBtn,
          el("span", { class: "spacer" }),
          clearBtn,
        ]),
      ]),
      // Right: vision + mic + asr
      el("div", { style: "display:flex; flex-direction:column; gap:8px; padding:12px; overflow-y:auto; min-width:0" }, [
        el("div", { style: "display:flex; gap:8px; align-items:center" }, [
          el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Jetson"),
          jetStatus,
        ]),
        jetImg,
        el("div", { class: "caps", style: "font-size:10px; color:var(--muted); margin-top:4px" }, "Сцена"),
        sceneCaption,
        el("div", { style: "display:flex; align-items:center; gap:8px; margin-top:4px" }, [
          el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Микрофон · OWW"),
          el("span", { class: "spacer" }),
          calibrateBtn,
        ]),
        eqCanvas,
        el("div", { style: "display:flex; align-items:center; gap:8px" }, [
          el("span", { class: "dim", style: "font-size:10px; color:var(--muted); line-height:1.4" },
            "Перетащи оранжевую линию, чтобы изменить порог wake-word. Циан — текущий OWW-score."),
          el("span", { class: "spacer" }),
          calibStatus,
        ]),
        el("div", { style: "display:flex; align-items:center; gap:6px; margin-top:4px" }, [
          hearingDot,
          el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Слух"),
        ]),
        asrBox,
      ]),
    ]),
  ]);

  target.appendChild(card);

  // Streaming Adam bubble: created by llm_partial events, finalized by adam_reply or send().
  let pendingAdamBubble = null;

  let pending = false;
  async function send() {
    const text = input.value.trim();
    if (!text || pending) return;
    pending = true;
    setState("отправка…");
    transcript.appendChild(bubble({ speaker: "viewer", text, ts: new Date().toISOString() }));
    input.value = "";
    scrollBottom();
    try {
      const result = await api.post("/api/agent/turn", { transcript: text });
      const finalBubble = bubble({
        speaker: "adam",
        text: result.reply || "(пусто)",
        ts: new Date().toISOString(),
        timings: result.timings,
        voice_degraded: result.voice_degraded,
      });
      if (pendingAdamBubble) {
        // Streaming bubble was created by llm_partial — replace with final version that has timings.
        transcript.replaceChild(finalBubble, pendingAdamBubble);
        pendingAdamBubble = null;
      } else {
        transcript.appendChild(finalBubble);
      }
      setState(result.voice_degraded ? "голос деградирован" : "ответ получен");
      scrollBottom();
    } catch (e) {
      transcript.appendChild(bubble({ speaker: "adam", text: `[ошибка] ${e.message}`, ts: new Date().toISOString() }));
      setState("ошибка");
    } finally { pending = false; }
  }

  function setState(text) {
    const node = document.getElementById("chat-state");
    if (node) node.textContent = text;
  }
  function scrollBottom() {
    requestAnimationFrame(() => { transcript.scrollTop = transcript.scrollHeight; });
  }

  api.get("/api/memory/dialogue?limit=40").then((data) => {
    (data.turns || []).forEach((turn) => transcript.appendChild(bubble(turn)));
    scrollBottom();
  }).catch((e) => console.error("history load failed", e));

  const unsubscribe = state.subscribe("last_events", (payload) => {
    const ev = payload.last;
    if (!ev) return;
    if (ev.type === "viewer_transcript" && ev.payload?.source === "voice_loop") {
      transcript.appendChild(bubble({ speaker: "viewer", text: ev.payload.text, ts: ev.ts }));
      scrollBottom();
    } else if (ev.type === "viewer_transcript" && ev.payload?.source === "barge_in") {
      transcript.appendChild(bubble({ speaker: "viewer", text: ev.payload.text, ts: ev.ts }));
      scrollBottom();
    } else if (ev.type === "llm_partial") {
      const text = ev.payload?.text || "";
      const idx = ev.payload?.index ?? 0;
      if (!text) return;
      if (idx === 0 || !pendingAdamBubble) {
        // First sentence: create a streaming Adam bubble with subtle opacity indicating in-progress.
        pendingAdamBubble = bubble({ speaker: "adam", text, ts: ev.ts });
        pendingAdamBubble.style.opacity = "0.75";
        transcript.appendChild(pendingAdamBubble);
      } else {
        // Append sentence to existing streaming bubble (children[1] = body div).
        const bodyEl = pendingAdamBubble.children[1];
        if (bodyEl) bodyEl.textContent += " " + text;
      }
      scrollBottom();
    } else if (ev.type === "adam_reply" && ev.payload?.source !== "manual") {
      const finalBubble = bubble({
        speaker: "adam", text: ev.payload.text, ts: ev.ts,
        timings: ev.payload.timings, voice_degraded: ev.payload.voice_degraded,
      });
      if (pendingAdamBubble) {
        // Replace streaming bubble with final version that has timings.
        transcript.replaceChild(finalBubble, pendingAdamBubble);
        pendingAdamBubble = null;
      } else {
        transcript.appendChild(finalBubble);
      }
      scrollBottom();
    } else if (ev.type === "audio_level") {
      eqServerLevel = typeof ev.payload?.level === "number" ? ev.payload.level : 0;
    } else if (ev.type === "oww_score") {
      wakeScore = typeof ev.payload?.score === "number" ? ev.payload.score : 0;
      // If the engine just published a fresh threshold (e.g. someone PATCHed
      // sensitivity from another tab), sync it — but NEVER while the local
      // user is mid-drag, or the handle would jump out from under them.
      if (!wakeDragging && typeof ev.payload?.threshold === "number") {
        wakeThreshold = ev.payload.threshold;
        wakeEngineReady = true;
      }
    } else if (ev.type === "wake_sensitivity_updated") {
      // Echo from our own PATCH or from a script (calibration). Reflect it.
      if (!wakeDragging && typeof ev.payload?.threshold === "number") {
        wakeThreshold = ev.payload.threshold;
      }
    } else if (ev.type === "scene_updated") {
      const text = ev.payload?.text || ev.payload?.summary || "";
      if (text) {
        sceneCaption.textContent = text + (ev.payload?.stale ? " (устарело)" : "");
        sceneCaption.style.color = "var(--text)";
      }
    } else if (ev.type === "barge_in") {
      // TTS was interrupted — discard any incomplete streaming bubble.
      pendingAdamBubble = null;
    } else if (ev.type === "voice_loop_started") {
      updateHearing("standby");
    } else if (ev.type === "voice_loop_stopped") {
      updateHearing("loading");
    } else if (ev.type === "wake_word_detected") {
      updateHearing("listening");
    } else if (ev.type === "asr_partial") {
      if (ev.payload?.state === "speech_started") updateHearing("listening");
    } else if (ev.type === "asr_reply_window_open") {
      updateHearing("reply");
    } else if (ev.type === "mic_muted" && ev.payload?.reason === "asr_transcribing") {
      updateHearing("transcribing");
    } else if (ev.type === "llm_thinking_started") {
      updateHearing("thinking");
    } else if (ev.type === "tts_started") {
      updateHearing("tts");
    } else if (ev.type === "tts_finished") {
      // Only exit if we're actually in "Говорю" — guards against stale
      // tts_finished from a previous turn flickering UI mid-flow.
      if (hearingState === "tts") routeToIdle();
    } else if (
      ev.type === "wake_silence_timeout" ||
      ev.type === "asr_no_reply_standby" ||
      ev.type === "reply_window_expired" ||
      ev.type === "asr_wake_only"
    ) {
      // These events terminate a pre-LLM listening/transcribing phase.
      // Skip if pipeline already advanced past them (LLM or TTS in flight).
      if (["listening", "reply", "transcribing"].includes(hearingState)) routeToIdle();
    } else if (ev.type === "llm_thinking_finished") {
      // Streaming pipeline often emits tts_started before LLM finishes — if we're
      // already in "tts", let it run. Only react if still in "thinking".
      if (hearingState === "thinking") routeToIdle();
    }
    // asr_final: no label override — mic_muted set "Распознаю", llm_thinking_started
    // will follow within milliseconds with "Думаю".
  });

  input.focus();
  return () => {
    unsubscribe();
    unsubScene();
    stopJetTimer();
    if (eqRafId) { cancelAnimationFrame(eqRafId); eqRafId = null; }
    if (dotsTimer) clearInterval(dotsTimer);
  };
}

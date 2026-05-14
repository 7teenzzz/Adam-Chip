import { api } from "../api.js";
import { state } from "../state.js";
import { toast } from "../widgets/toast.js";
import { createWakeMeter, createCalibrateButton } from "../widgets/wakeMeter.js";

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

const CAMERA_LABELS = {
  esp_mjpeg:        "ESP32 CAM",
  jetson_gstreamer: "Jetson",
  remote_rtsp:      "RTSP",
};

function cameraSourceLabel(primary) {
  return CAMERA_LABELS[primary] || (primary ? primary : "камера");
}

export function mount(target) {
  // ---- Vision (right panel) ----
  const jetImg = el("img", {
    alt: "camera snapshot",
    style: "width:100%; max-height:240px; object-fit:contain; border-radius:var(--radius-s); border:1px solid var(--line); background:var(--bg-2); display:block",
  });
  const jetStatus = el("span", { style: "font-size:10px; color:var(--muted); font-family:var(--font-mono)" }, "—");
  const cameraLabel = el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "камера");
  const sceneCaption = el("div", { style: "color:var(--muted); font-size:12px; white-space:pre-wrap; line-height:1.5" }, "Сцена не описана.");

  // ---- Wake-word meter (read-only on chat panel) ----
  // Shows what Adam hears: live audio_level bars + current OWW score (cyan
  // line) + threshold marker (orange dashed). The slider/drag interaction
  // lives on the Settings page; here we only visualise.
  const wakeMeter = createWakeMeter({ draggable: false, height: 96 });
  const eqCanvas = wakeMeter.canvas;

  const vuCanvas = el("canvas", {
    style: "width:44px; flex-shrink:0; height:52px; border-radius:4px; display:block; background:var(--bg-2)",
  });
  let vuChannels = 1;
  let vuLevelL = 0, vuLevelR = 0, vuLevelMono = 0;
  let vuPeakL = 0,  vuPeakR = 0,  vuPeakMono = 0;
  let vuRafId = null;

  function drawVuMeter() {
    const dpr = window.devicePixelRatio || 1;
    const rect = vuCanvas.getBoundingClientRect();
    if (rect.width > 0) {
      const cw = Math.round(rect.width * dpr), ch = Math.round(rect.height * dpr);
      if (vuCanvas.width !== cw || vuCanvas.height !== ch) {
        vuCanvas.width = cw; vuCanvas.height = ch;
      }
      const ctx = vuCanvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = rect.width, h = rect.height;
      ctx.clearRect(0, 0, w, h);

      const isStereo = vuChannels === 2;
      const GAP = isStereo ? 4 : 0;
      const barW = isStereo ? (w - GAP) / 2 : w;

      function drawBar(x, level, peak) {
        ctx.fillStyle = "rgba(67,209,122,0.10)";
        ctx.fillRect(Math.round(x), h - 2, Math.round(barW), 2);
        const newPeak = Math.max(level, peak * 0.90);
        const bh = Math.max(1, newPeak * (h - 4));
        ctx.fillStyle = `rgba(67,209,122,${0.35 + newPeak * 0.65})`;
        ctx.fillRect(Math.round(x), Math.round(h - 2 - bh), Math.round(barW), Math.round(bh));
        return newPeak;
      }

      if (isStereo) {
        vuPeakL = drawBar(0, vuLevelL, vuPeakL);
        vuPeakR = drawBar(barW + GAP, vuLevelR, vuPeakR);
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.fillStyle = "rgba(67,209,122,0.45)";
        ctx.font = "9px var(--font-mono, monospace)";
        ctx.fillText("L", 2, h - 3);
        ctx.fillText("R", Math.round((barW + GAP) * dpr) + 2, h - 3);
      } else {
        vuPeakMono = drawBar(0, vuLevelMono, vuPeakMono);
      }
    }
    vuRafId = requestAnimationFrame(drawVuMeter);
  }
  vuRafId = requestAnimationFrame(drawVuMeter);

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

  const countdownTrack = el("div", {
    style: "width:100%; height:3px; background:rgba(67,209,122,0.12); border-radius:2px; overflow:hidden; margin-top:2px",
  });
  const countdownFill = el("div", {
    style: "height:100%; width:0%; background:var(--accent); border-radius:2px; transition:none",
  });
  countdownTrack.appendChild(countdownFill);
  let _cdTimer = null;

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

  function startCountdown(durationMs) {
    if (_cdTimer) { clearTimeout(_cdTimer); _cdTimer = null; }
    countdownFill.style.transition = "none";
    countdownFill.style.width = "100%";
    requestAnimationFrame(() => requestAnimationFrame(() => {
      countdownFill.style.transition = `width ${durationMs}ms linear`;
      countdownFill.style.width = "0%";
    }));
    _cdTimer = setTimeout(stopCountdown, durationMs + 100);
  }

  function stopCountdown() {
    if (_cdTimer) { clearTimeout(_cdTimer); _cdTimer = null; }
    countdownFill.style.transition = "none";
    countdownFill.style.width = "0%";
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
  function paintCameraLabel() {
    const primary = state.get("status")?.media?.video?.primary;
    cameraLabel.textContent = cameraSourceLabel(primary);
  }
  const unsubScene = state.subscribe("status", () => { paintScene(); paintCameraLabel(); });
  paintScene();
  paintCameraLabel();
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

  // ---- Wake-word noise calibration ----
  // Shared widget — same button lives on the Settings page too.
  const { btn: calibrateBtn, status: calibStatus } = createCalibrateButton();

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
          cameraLabel,
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
        el("div", { style: "display:flex; gap:6px; align-items:stretch" }, [
          el("div", { style: "flex:1; min-width:0" }, [eqCanvas]),
          vuCanvas,
        ]),
        el("div", { style: "display:flex; align-items:center; gap:8px" }, [
          el("span", { class: "dim", style: "font-size:10px; color:var(--muted); line-height:1.4" },
            "Оранжевый — порог wake-word, циан — текущий OWW-score. Настройка порога — в разделе Настройки → OWW."),
          el("span", { class: "spacer" }),
          calibStatus,
        ]),
        el("div", { style: "display:flex; align-items:center; gap:6px; margin-top:4px" }, [
          hearingDot,
          el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Слух"),
        ]),
        asrBox,
        countdownTrack,
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
      if (ev.payload?.channels === 2) {
        vuChannels = 2;
        vuLevelL = ev.payload.level_l ?? 0;
        vuLevelR = ev.payload.level_r ?? 0;
      } else {
        vuChannels = 1;
        vuLevelMono = ev.payload?.level ?? 0;
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
      stopCountdown();
    } else if (ev.type === "voice_loop_started") {
      updateHearing("standby");
    } else if (ev.type === "voice_loop_stopped") {
      updateHearing("loading");
      stopCountdown();
    } else if (ev.type === "wake_word_detected") {
      updateHearing("listening");
      startCountdown((ev.payload?.silence_timeout_sec ?? 6) * 1000);
    } else if (ev.type === "endpointing_started") {
      startCountdown(ev.payload?.duration_ms ?? 3000);
    } else if (ev.type === "asr_partial") {
      if (ev.payload?.state === "speech_started") {
        updateHearing("listening");
        stopCountdown();
      }
    } else if (ev.type === "asr_reply_window_open") {
      updateHearing("reply");
      startCountdown((ev.payload?.timeout_sec ?? 4) * 1000);
    } else if (ev.type === "mic_muted" && ev.payload?.reason === "asr_transcribing") {
      updateHearing("transcribing");
      stopCountdown();
    } else if (ev.type === "llm_thinking_started") {
      updateHearing("thinking");
    } else if (ev.type === "tts_started") {
      updateHearing("tts");
      stopCountdown();
    } else if (ev.type === "tts_finished") {
      if (hearingState === "tts") routeToIdle();
    } else if (
      ev.type === "wake_silence_timeout" ||
      ev.type === "asr_no_reply_standby" ||
      ev.type === "reply_window_expired" ||
      ev.type === "asr_wake_only"
    ) {
      if (["listening", "reply", "transcribing"].includes(hearingState)) {
        routeToIdle();
        stopCountdown();
      }
    } else if (ev.type === "llm_thinking_finished") {
      if (hearingState === "thinking") routeToIdle();
    }
    // asr_final: no label override — mic_muted set transcribing, llm_thinking_started follows.
  });

  input.focus();
  return () => {
    unsubscribe();
    unsubScene();
    stopJetTimer();
    if (wakeMeter && typeof wakeMeter.dispose === "function") wakeMeter.dispose();
    if (vuRafId) { cancelAnimationFrame(vuRafId); vuRafId = null; }
    if (dotsTimer) clearInterval(dotsTimer);
    stopCountdown();
  };
}

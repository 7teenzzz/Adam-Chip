import { api } from "../api.js";
import { state } from "../state.js";
import { toast } from "../widgets/toast.js";
import { createWakeMeter } from "../widgets/wakeMeter.js";

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

  // Phase 9 (REQ-UI-CHAT-CLEANUP): VU-meter height matches equalizer (96 px)
  // so the two bars align visually.
  const vuCanvas = el("canvas", {
    style: "width:44px; flex-shrink:0; height:96px; border-radius:4px; display:block; background:var(--bg-2)",
  });
  let vuChannels = 1;
  let vuLevelL = 0, vuLevelR = 0, vuLevelMono = 0;
  let vuPeakL = 0,  vuPeakR = 0,  vuPeakMono = 0;
  let vuRafId = null;

  // Mic source badge — single source of truth is the server snapshot.
  // Initial value comes from /api/agent/status (voice_loop.mic_active_source).
  // Live updates arrive via audio_level SSE events. Pre-snapshot we show "—"
  // instead of lying with a default "local" label.
  const initialVL = state.get("status")?.voice_loop;
  // Plan 07-04: hide Mic plate during boot_warmup or when voice_loop is down —
  // the badge must not lie about an active ESP32 stream before standby.
  const _initialVlBoot =
    !initialVL || !initialVL.running || initialVL.voice_state === "boot_warmup";
  let micSource = _initialVlBoot ? null : (initialVL.mic_active_source || null);
  const micSourceBadge = el("span", {
    style: "font-size:10px; color:var(--muted); font-family:var(--font-mono); padding:2px 6px; border-radius:3px; background:var(--bg-2)",
  }, "Mic: —");
  // Equaliser colour tracks the mic source so the user never confuses an
  // ESP32 stream with the local fallback.
  //   esp32_stereo / esp32_mono → green (--accent path)
  //   local_fallback            → amber/warn (ESP32 down)
  //   local                     → muted grey (idle equaliser, no pipeline)
  //   null / unknown            → "—", pre-snapshot
  function vuColorTriplet() {
    if (micSource === "esp32_stereo" || micSource === "esp32_mono") {
      return { rgb: "67,209,122", emoji: "🟢", label: micSource === "esp32_stereo" ? "ESP32 stereo" : "ESP32 mono" };
    }
    if (micSource === "local_fallback") {
      return { rgb: "240,184,74", emoji: "🟡", label: "Local (ESP32 down)" };
    }
    if (micSource === "local") {
      return { rgb: "150,150,160", emoji: "⚪", label: "Local" };
    }
    return { rgb: "120,120,130", emoji: "○", label: "—" };
  }
  function refreshMicSourceBadge() {
    const c = vuColorTriplet();
    micSourceBadge.textContent = `${c.emoji} Mic: ${c.label}`;
    micSourceBadge.style.color = `rgb(${c.rgb})`;
  }
  refreshMicSourceBadge();

  function drawVuMeter() {
    // REQ-UI-INIT-STATUS: while UI is in loading/boot_warmup (or before any
    // mic source is known), equaliser and VU-meter render a flat placeholder.
    // Mic plate badge separately stays "—" via refreshMicSourceBadge.
    if (hearingState === "loading" || hearingState === "boot_warmup" || !micSource) {
      const rect2 = vuCanvas.getBoundingClientRect();
      if (rect2.width > 0) {
        const dpr2 = window.devicePixelRatio || 1;
        const cw2 = Math.round(rect2.width * dpr2);
        const ch2 = Math.round(rect2.height * dpr2);
        if (vuCanvas.width !== cw2 || vuCanvas.height !== ch2) {
          vuCanvas.width = cw2; vuCanvas.height = ch2;
        }
        const ctx2 = vuCanvas.getContext("2d");
        ctx2.setTransform(dpr2, 0, 0, dpr2, 0, 0);
        ctx2.clearRect(0, 0, rect2.width, rect2.height);
        ctx2.fillStyle = "rgba(120,120,130,0.18)";
        ctx2.fillRect(0, rect2.height - 2, rect2.width, 2);
      }
      vuRafId = requestAnimationFrame(drawVuMeter);
      return;
    }
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
      const barRgb = vuColorTriplet().rgb;  // T17 fix #8 — colour by source

      function drawBar(x, level, peak) {
        ctx.fillStyle = `rgba(${barRgb},0.10)`;
        ctx.fillRect(Math.round(x), h - 2, Math.round(barW), 2);
        const newPeak = Math.max(level, peak * 0.90);
        const bh = Math.max(1, newPeak * (h - 4));
        ctx.fillStyle = `rgba(${barRgb},${0.35 + newPeak * 0.65})`;
        ctx.fillRect(Math.round(x), Math.round(h - 2 - bh), Math.round(barW), Math.round(bh));
        return newPeak;
      }

      if (isStereo) {
        vuPeakL = drawBar(0, vuLevelL, vuPeakL);
        vuPeakR = drawBar(barW + GAP, vuLevelR, vuPeakR);
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.fillStyle = `rgba(${barRgb},0.45)`;
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
  // State machine is server-authoritative: on mount we read /api/agent/status
  // and derive the initial label. Pre-snapshot we show "unknown" (a neutral
  // grey "—" placeholder) instead of lying with "Инициализация" — the latter
  // is reserved for the case where the snapshot HAS loaded and voice_loop
  // is actually down. Transitions are driven by SSE events.
  const HEARING_COLORS = {
    unknown:      "var(--dim)",    // grey    — snapshot not loaded yet
    loading:      "var(--warn)",   // yellow  — voice_loop down (real)
    boot_warmup:  "var(--warn)",   // yellow  — mic active but warmup in progress (OWW not scanning)
    standby:      "var(--accent)", // green   — waiting for wake word
    listening:    "#a855f7",       // purple  — recording / accumulating speech
    reply:        "#a855f7",       // purple  — reply window open (same as listening)
    transcribing: "#f0b84a",       // amber   — WhisperX processing
    thinking:     "#22d3ee",       // cyan    — LLM generating
    tts:          "#60a5fa",       // blue    — Adam is speaking
  };
  // W-4 fix: both `loading` and `boot_warmup` show identical text. They differ
  // semantically (loading = voice_loop down; boot_warmup = up but pre-standby
  // drain mode), which matters for state-machine routing but NOT for the label.
  const HEARING_LABELS = {
    unknown:      "— ожидаем данных",
    loading:      "⌛ Инициализация",
    boot_warmup:  "⌛ Инициализация",
    standby:      "💤 Ожидаю обращения",
    listening:    "🎤 Слушаю",
    reply:        "🎤 Слушаю",
    transcribing: "⏳ Распознаю",
    thinking:     "💭 Думаю",
    tts:          "🔊 Говорю",
  };
  let hearingState = (() => {
    const vl = state.get("status")?.voice_loop;
    if (vl == null) return "unknown";
    if (!vl.running) return "loading";
    // Honour boot_warmup: voice_loop is up but still in warmup TTS.
    const vs = vl.voice_state;
    if (vs === "boot_warmup") return "boot_warmup";
    if (vs === "listening" || vs === "reply") return vs;
    return "standby";
  })();
  let dotsTick = 0;
  const DOTS_PERIOD_MS = 400;
  const hearingDot = el("span", {
    style: `display:inline-block; width:8px; height:8px; border-radius:50%;
            background:${HEARING_COLORS[hearingState] || HEARING_COLORS.unknown}; flex-shrink:0; transition:background 0.35s`,
  });
  const asrBox = el("div", {
    style: "min-height:28px; padding:6px 8px; border-radius:4px; background:var(--bg-2); font-size:12px; color:var(--muted); font-family:var(--font-mono); white-space:pre-wrap; word-break:break-word; line-height:1.4",
  }, HEARING_LABELS[hearingState] || HEARING_LABELS.unknown);

  // ---- Countdown bar ----
  const countdownFill = el("div", {
    style: "height:100%; width:0%; background:var(--accent); border-radius:2px; transition:none",
  });
  const countdownTrack = el("div", {
    style: "width:100%; height:3px; background:rgba(67,209,122,0.12); border-radius:2px; overflow:hidden",
  }, [countdownFill]);
  let _cdTimer = null;

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

  function renderHearing() {
    asrBox.textContent = (HEARING_LABELS[hearingState] || "—") + ".".repeat(dotsTick);
  }
  function tickDots() {
    dotsTick = (dotsTick + 1) % 4;   // 0,1,2,3 → "" "." ".." "..."
    renderHearing();
  }
  const dotsTimer = setInterval(tickDots, DOTS_PERIOD_MS);

  function updateHearing(newState) {
    const prev = hearingState;
    hearingState = newState;
    hearingDot.style.background = HEARING_COLORS[newState] || "var(--muted)";
    asrBox.style.color = (newState === "loading" || newState === "boot_warmup")
      ? "var(--muted)"
      : "var(--text)";
    // Plan 07-04: leaving boot_warmup means MicReader is now reporting a real
    // standby/listening/reply state — pull mic_active_source from the snapshot
    // so the badge flips green immediately, without waiting for the next poll.
    if (prev === "boot_warmup" && newState !== "boot_warmup" && newState !== "loading") {
      const vlSnap = state.get("status")?.voice_loop;
      const src = vlSnap?.mic_active_source || null;
      if (src && src !== micSource) {
        micSource = src;
        refreshMicSourceBadge();
      }
    }
    dotsTick = 0;
    renderHearing();
  }

  // Route to idle: standby if voice_loop is up, loading if it's down,
  // unknown if we don't have a snapshot yet. Called when an active SSE
  // state ends or on initial mount before any events arrive.
  function routeToIdle() {
    const vl = state.get("status")?.voice_loop;
    if (vl == null) { updateHearing("unknown"); return; }
    if (!vl.running) { updateHearing("loading"); return; }
    const vs = vl.voice_state;
    if (vs === "boot_warmup") { updateHearing("boot_warmup"); return; }
    updateHearing("standby");
  }

  // Polling-time sync — preserves active SSE-driven states so polling
  // never overrides "слушаю / распознаю / думаю / говорю" mid-flow.
  function syncHearingFromStatus() {
    if (["listening", "reply", "transcribing", "thinking", "tts", "boot_warmup"].includes(hearingState)) return;
    // Also refresh mic source from snapshot — keeps badge truthful across
    // remounts when no audio_level event has fired since last navigation.
    const vlSnap = state.get("status")?.voice_loop;
    if (vlSnap?.mic_active_source && vlSnap.mic_active_source !== micSource) {
      micSource = vlSnap.mic_active_source;
      refreshMicSourceBadge();
    }
    routeToIdle();
  }
  syncHearingFromStatus();
  state.subscribe("status", syncHearingFromStatus);

  // Self-trigger a status fetch on mount so we don't wait for main.js's
  // 4-second polling cycle to deliver the first snapshot.
  if (state.get("status") == null) {
    api.get("/api/agent/status").then((s) => state.set("status", s)).catch(() => {});
  }

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

  // Phase 9 (REQ-UI-CHAT-CLEANUP): calibrate button removed from chat panel.
  // The shared widget still lives on the Settings page (settings.js) — that
  // is the canonical place to recalibrate noise threshold.

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
        // Phase 9 (REQ-UI-CHAT-CLEANUP): mic-source badge moved up into the
        // header row (right-aligned, where the calibrate button used to live).
        el("div", { style: "display:flex; align-items:center; gap:8px; margin-top:4px" }, [
          el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Микрофон · OWW"),
          el("span", { class: "spacer" }),
          micSourceBadge,
        ]),
        el("div", { style: "display:flex; gap:6px; align-items:stretch" }, [
          el("div", { style: "flex:1; min-width:0" }, [eqCanvas]),
          vuCanvas,
        ]),
        el("div", { style: "display:flex; align-items:center; gap:8px" }, [
          el("span", { class: "dim", style: "font-size:10px; color:var(--muted); line-height:1.4" },
            "Оранжевый — порог wake-word, циан — текущий OWW-score. Настройка порога — в разделе Настройки → OWW."),
          el("span", { class: "spacer" }),
        ]),
        el("div", { style: "display:flex; align-items:center; gap:6px; margin-top:4px" }, [
          hearingDot,
          el("span", { class: "caps", style: "font-size:10px; color:var(--muted)" }, "Статус речевого модуля"),
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
      // Plan 07-04: during boot_warmup/loading the Mic plate stays "—".
      // We still update vuLevel* so transitioning out of boot shows fresh data,
      // but the badge must not flip to "🟢 Mic: ESP32 stereo" before standby.
      if (hearingState === "boot_warmup" || hearingState === "loading") {
        // Skip mic source badge refresh — voice_state_change(to=standby)
        // will pull mic_active_source from the snapshot.
      } else {
        // T17 fix #7 — refresh source badge live from per-event tag.
        const incomingSource = ev.payload?.source;
        if (incomingSource && incomingSource !== micSource) {
          micSource = incomingSource;
          refreshMicSourceBadge();
        }
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
      // Phase 7: voice_loop now starts in boot_warmup. Trust the explicit
      // voice_state_change(to=...) event for the real transition rather than
      // assuming standby here. Payload is the full status() dict.
      const vs = ev.payload && ev.payload.voice_state;
      updateHearing(vs === "boot_warmup" ? "boot_warmup" : "standby");
    } else if (ev.type === "voice_state_change") {
      // boot_warmup → standby is the warmup-done transition. Other transitions
      // (standby ↔ listening, listening → reply, reply → standby) are handled
      // by their dedicated SSE events (wake_word_detected, asr_reply_window_open,
      // etc.) — we do not double-handle them here.
      const to = ev.payload && ev.payload.to;
      const from = ev.payload && ev.payload.from;
      if (to === "boot_warmup") {
        updateHearing("boot_warmup");
      } else if (from === "boot_warmup" && to === "standby") {
        updateHearing("standby");
      }
    } else if (ev.type === "voice_loop_stopped") {
      updateHearing("loading");
      stopCountdown();
    } else if (ev.type === "wake_word_detected") {
      updateHearing("listening");
      startCountdown((ev.payload?.silence_timeout_sec ?? 5) * 1000);
    } else if (ev.type === "asr_partial") {
      if (ev.payload?.state === "speech_started") {
        updateHearing("listening");
        stopCountdown();
      }
    } else if (ev.type === "endpointing_started") {
      startCountdown(ev.payload?.duration_ms ?? 3500);
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
      if (["listening", "reply", "transcribing"].includes(hearingState)) routeToIdle();
      stopCountdown();
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

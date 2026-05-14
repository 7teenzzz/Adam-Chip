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

  // ---- Equalizer — driven by server-side audio_level SSE events ----
  // Shows what Adam actually hears from the Jetson ALSA mic. No browser mic needed.
  const eqCanvas = el("canvas", {
    style: "width:100%; height:52px; border-radius:4px; display:block; background:var(--bg-2)",
  });
  const BAR_N = 28;
  const eqPeaks = new Float32Array(BAR_N);
  let eqServerLevel = 0;   // latest normalized level (0–1) from audio_level SSE event
  let eqRafId = null;

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
    }
    eqRafId = requestAnimationFrame(drawEqualizer);
  }
  eqRafId = requestAnimationFrame(drawEqualizer);

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
  let hearingState = "loading";
  const hearingDot = el("span", {
    style: `display:inline-block; width:8px; height:8px; border-radius:50%;
            background:${HEARING_COLORS.loading}; flex-shrink:0; transition:background 0.35s`,
  });
  const asrBox = el("div", {
    style: "min-height:28px; padding:6px 8px; border-radius:4px; background:var(--bg-2); font-size:12px; color:var(--muted); font-family:var(--font-mono); white-space:pre-wrap; word-break:break-word; line-height:1.4",
  }, "OWW / ASR инициализация…");
  let asrClearTimer = null;

  function standbyText() {
    const vl = state.get("status")?.voice_loop;
    if (!vl?.running) return "OWW / ASR инициализация…";
    const words = vl.wake_words?.length ? vl.wake_words : null;
    return words ? `ожидание «${words.join(" / ")}»` : "ожидание…";
  }

  function updateHearing(newState, text) {
    hearingState = newState;
    hearingDot.style.background = HEARING_COLORS[newState] || "var(--muted)";
    if (text !== undefined) {
      asrBox.textContent = text;
      asrBox.style.color = newState === "loading" ? "var(--muted)" : "var(--text)";
    }
  }

  // Sync dot from current status snapshot on load
  function syncHearingFromStatus() {
    const vl = state.get("status")?.voice_loop;
    if (!vl?.running) { updateHearing("loading", standbyText()); return; }
    updateHearing("standby", standbyText());
    asrBox.style.color = "var(--muted)";
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
        el("div", { class: "caps", style: "font-size:10px; color:var(--muted); margin-top:4px" }, "Микрофон"),
        eqCanvas,
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
      updateHearing("standby", standbyText());
      asrBox.style.color = "var(--muted)";
    } else if (ev.type === "voice_loop_stopped") {
      updateHearing("loading", "OWW / ASR инициализация…");
    } else if (ev.type === "wake_word_detected") {
      if (asrClearTimer) { clearTimeout(asrClearTimer); asrClearTimer = null; }
      updateHearing("listening", "🎤 слушаю…");
    } else if (ev.type === "asr_partial") {
      if (ev.payload?.state === "speech_started") {
        if (asrClearTimer) { clearTimeout(asrClearTimer); asrClearTimer = null; }
        updateHearing("listening", "🎤 слушаю…");
      }
    } else if (ev.type === "asr_reply_window_open") {
      updateHearing("reply", "🎤 слушаю…");
    } else if (ev.type === "mic_muted" && ev.payload?.reason === "asr_transcribing") {
      updateHearing("transcribing", "⏳ распознаю…");
    } else if (ev.type === "llm_thinking_started") {
      updateHearing("thinking", "💭 думает…");
    } else if (ev.type === "llm_thinking_finished") {
      if (hearingState === "thinking") updateHearing("standby", standbyText());
    } else if (ev.type === "tts_started") {
      if (asrClearTimer) { clearTimeout(asrClearTimer); asrClearTimer = null; }
      updateHearing("tts", "🔊 говорит…");
    } else if (ev.type === "tts_finished") {
      updateHearing("standby", standbyText());
      asrBox.style.color = "var(--muted)";
    } else if (ev.type === "asr_wake_only") {
      updateHearing("standby", `«${ev.payload?.raw || "—"}» — только wake word`);
      asrBox.style.color = "var(--muted)";
      if (asrClearTimer) clearTimeout(asrClearTimer);
      asrClearTimer = setTimeout(() => { updateHearing("standby", standbyText()); asrBox.style.color = "var(--muted)"; asrClearTimer = null; }, 5000);
    } else if (ev.type === "asr_final") {
      const text = ev.payload?.text || "";
      updateHearing("listening", text || standbyText());
      asrBox.style.color = text ? "var(--text)" : "var(--muted)";
      if (asrClearTimer) clearTimeout(asrClearTimer);
      asrClearTimer = setTimeout(() => {
        if (hearingState !== "tts") updateHearing("standby", standbyText());
        asrBox.style.color = "var(--muted)";
        asrClearTimer = null;
      }, 10000);
    }
  });

  input.focus();
  return () => {
    unsubscribe();
    unsubScene();
    stopJetTimer();
    if (eqRafId) { cancelAnimationFrame(eqRafId); eqRafId = null; }
    if (asrClearTimer) { clearTimeout(asrClearTimer); asrClearTimer = null; }
  };
}

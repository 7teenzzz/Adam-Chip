import { api } from "../api.js";
import { state } from "../state.js";
import { toast } from "../widgets/toast.js";
import { encodeWav } from "../widgets/wav.js";

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
  if (value == null) return "—";
  if (value >= 1000) return `${(value / 1000).toFixed(2)}с`;
  return `${Math.round(value)}мс`;
}

export function mount(target) {
  const stateLabel = el("div", { class: "caps", id: "voice-state", style: "color:var(--muted); letter-spacing:0.1em" }, "ОЖИДАНИЕ");
  const ptt = el("button", {
    class: "btn",
    id: "voice-ptt",
    style: "width:180px; height:180px; border-radius:50%; font-size:18px; font-family:var(--font-mono); letter-spacing:0.08em; padding:0; flex-direction:column; gap:4px",
    title: "Зажми и говори (или пробел)",
  }, [
    el("span", { style: "font-size:28px" }, "●"),
    el("span", null, "PUSH-TO-TALK"),
  ]);
  const canvas = el("canvas", { id: "voice-wave", width: 600, height: 80, style: "width:100%; max-width:520px; height:80px; background:var(--bg-2); border:1px solid var(--line); border-radius:var(--radius-s)" });
  const transcriptCard = el("div", { class: "card", id: "voice-transcript", style: "display:none" });
  const replyCard = el("div", { class: "card", id: "voice-reply", style: "display:none" });
  const continuousToggle = el("label", { class: "row", style: "gap:8px; cursor:pointer" }, [
    el("input", { type: "checkbox", id: "voice-vad-toggle", style: "accent-color:var(--accent)" }),
    el("span", { class: "caps", style: "color:var(--muted)" }, "Авто-VAD (бета)"),
  ]);
  const wakeStatus = el("div", { class: "caps", id: "voice-wake", style: "color:var(--muted)" }, "");

  target.appendChild(el("section", { class: "col" }, [
    el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Голос"),
        wakeStatus,
      ]),
      el("div", { class: "card-body", style: "display:flex; flex-direction:column; align-items:center; gap:18px; padding:32px" }, [
        ptt,
        stateLabel,
        canvas,
        el("div", { class: "row", style: "gap:16px" }, [
          continuousToggle,
        ]),
        el("div", { class: "muted", style: "font-size:12px; max-width:520px; text-align:center" },
          "Зажми кнопку и говори. Отпусти — отправится в Whisper. Если в настройках включено wake-word, фраза должна начинаться с «Адам»."),
      ]),
    ]),
    transcriptCard,
    replyCard,
  ]));

  // Wake-word indicator from /api/agent/status snapshot.
  function paintWake() {
    const vl = state.get("status")?.voice_loop;
    if (!vl) return;
    if (vl.wake_word_required && vl.wake_words?.length) {
      const words = Array.isArray(vl.wake_words) ? vl.wake_words : [vl.wake_words];
      wakeStatus.textContent = `wake: ${words.join(" / ")}`;
    } else {
      wakeStatus.textContent = "wake: off";
    }
  }
  paintWake();
  const unsub = state.subscribe("status", paintWake);

  const setState = (text, kind = "muted") => {
    stateLabel.textContent = text.toUpperCase();
    stateLabel.style.color = ({
      muted: "var(--muted)",
      ok: "var(--accent)",
      warn: "var(--warn)",
      bad: "var(--bad)",
      pulse: "var(--accent)",
    })[kind] || "var(--muted)";
  };

  function showTranscript(text, asrMs) {
    transcriptCard.style.display = "";
    transcriptCard.innerHTML = "";
    transcriptCard.appendChild(el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Транскрипт"),
      el("span", { class: "caps mono", style: "color:var(--accent)" }, `ASR ${fmtMs(asrMs)}`),
    ]));
    transcriptCard.appendChild(el("div", { class: "card-body" }, text || "(пусто)"));
  }

  function showReply(turn) {
    replyCard.style.display = "";
    replyCard.innerHTML = "";
    const t = turn?.timings || {};
    replyCard.appendChild(el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Адам"),
      el("span", { class: "caps mono", style: "color:var(--accent)" },
        `LLM ${fmtMs(t.llm_ms)} · TTS ${fmtMs(t.tts_ms)} · ∑ ${fmtMs(t.total_ms)}`),
    ]));
    replyCard.appendChild(el("div", { class: "card-body" }, turn.reply || "(пусто)"));
  }

  function showWakeSkip(text) {
    transcriptCard.style.display = "";
    transcriptCard.innerHTML = "";
    transcriptCard.appendChild(el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Транскрипт"),
      el("span", { class: "caps", style: "color:var(--warn)" }, "пропущено: нет wake-word"),
    ]));
    transcriptCard.appendChild(el("div", { class: "card-body muted" }, text));
    replyCard.style.display = "none";
  }

  // ---- Recording infrastructure ----------------------------------------
  let stream = null;
  let recorder = null;
  let chunks = [];
  let analyser = null;
  let waveCtx = canvas.getContext("2d");
  let waveTimer = null;
  let busy = false;

  async function ensureStream() {
    if (stream) return stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, sampleRate: 16000, noiseSuppression: true, echoCancellation: true },
        video: false,
      });
    } catch (e) {
      toast("Микрофон недоступен: " + e.message, "bad", 6000);
      throw e;
    }
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(analyser);
    return stream;
  }

  function drawWave() {
    if (!analyser) return;
    const buf = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(buf);
    const w = canvas.width;
    const h = canvas.height;
    waveCtx.clearRect(0, 0, w, h);
    waveCtx.lineWidth = 2;
    waveCtx.strokeStyle = recorder?.state === "recording" ? "#43d17a" : "#3a3a48";
    waveCtx.beginPath();
    const step = w / buf.length;
    for (let i = 0; i < buf.length; i++) {
      const v = buf[i] / 128 - 1;
      const y = h / 2 + v * h / 2;
      if (i === 0) waveCtx.moveTo(i * step, y);
      else waveCtx.lineTo(i * step, y);
    }
    waveCtx.stroke();
  }

  function startWaveLoop() {
    if (waveTimer) return;
    waveTimer = setInterval(drawWave, 50);
  }
  function stopWaveLoop() {
    if (!waveTimer) return;
    clearInterval(waveTimer);
    waveTimer = null;
    waveCtx.clearRect(0, 0, canvas.width, canvas.height);
  }

  async function startRecording() {
    if (busy || recorder?.state === "recording") return;
    try {
      await ensureStream();
    } catch (_) { return; }
    chunks = [];
    const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"]
      .find((t) => MediaRecorder.isTypeSupported(t)) || "";
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
    recorder.ondataavailable = (ev) => { if (ev.data && ev.data.size) chunks.push(ev.data); };
    recorder.onstop = handleRecordedAudio;
    recorder.start();
    setState("запись", "pulse");
    ptt.classList.add("pulse-loud");
    startWaveLoop();
  }

  async function stopRecording() {
    if (!recorder || recorder.state !== "recording") return;
    setState("обработка…", "warn");
    ptt.classList.remove("pulse-loud");
    recorder.stop();
  }

  async function handleRecordedAudio() {
    const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    chunks = [];
    if (blob.size < 1500) {
      setState("слишком коротко", "warn");
      stopWaveLoop();
      setTimeout(() => setState("ожидание"), 1500);
      return;
    }
    busy = true;
    try {
      const wav = await encodeWav(blob, 16000);
      setState("транскрибируем…", "warn");
      const result = await fetch("/api/agent/asr/upload?auto_turn=true", {
        method: "POST",
        headers: { "Content-Type": "audio/wav" },
        body: wav,
      });
      if (!result.ok) {
        const detail = await result.text();
        throw new Error(`HTTP ${result.status}: ${detail.slice(0, 160)}`);
      }
      const data = await result.json();
      if (data.transcript) {
        showTranscript(data.transcript, data.turn?.timings?.asr_ms);
      }
      if (data.turn?.ok) {
        showReply(data.turn);
        setState("готово", "ok");
      } else if (!data.transcript) {
        showWakeSkip("(тишина или ничего не распознано)");
        setState("ничего", "warn");
      } else {
        // transcript есть, но turn не запустился — например wake-word skip.
        showWakeSkip(data.transcript);
        setState("пропущено", "warn");
      }
    } catch (e) {
      toast(e.message, "bad", 5000);
      setState("ошибка", "bad");
    } finally {
      busy = false;
      stopWaveLoop();
      setTimeout(() => { if (!busy && recorder?.state !== "recording") setState("ожидание"); }, 2000);
    }
  }

  // ---- Bindings: mouse / touch / keyboard ------------------------------
  ptt.addEventListener("mousedown", (e) => { e.preventDefault(); startRecording(); });
  ptt.addEventListener("mouseup",   (e) => { e.preventDefault(); stopRecording(); });
  ptt.addEventListener("mouseleave", () => { if (recorder?.state === "recording") stopRecording(); });
  ptt.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); }, { passive: false });
  ptt.addEventListener("touchend",   (e) => { e.preventDefault(); stopRecording(); }, { passive: false });

  function onKeyDown(e) {
    if (e.code !== "Space" || e.repeat) return;
    if (document.activeElement && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    e.preventDefault();
    startRecording();
  }
  function onKeyUp(e) {
    if (e.code !== "Space") return;
    if (document.activeElement && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    e.preventDefault();
    stopRecording();
  }
  document.addEventListener("keydown", onKeyDown);
  document.addEventListener("keyup", onKeyUp);

  // ---- Continuous VAD (very light): trigger when RMS sustained ---------
  let vadTimer = null;
  function startVadLoop() {
    if (vadTimer) return;
    let aboveSince = 0;
    let belowSince = 0;
    const threshold = 0.025;
    const enterMs = 200;
    const exitMs = 700;
    vadTimer = setInterval(() => {
      if (!analyser) {
        ensureStream().catch(() => {});
        return;
      }
      const buf = new Float32Array(analyser.fftSize);
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);
      const now = performance.now();
      const recording = recorder?.state === "recording";
      if (rms > threshold) {
        if (!aboveSince) aboveSince = now;
        belowSince = 0;
        if (!recording && !busy && now - aboveSince > enterMs) startRecording();
      } else {
        if (recording) {
          if (!belowSince) belowSince = now;
          if (now - belowSince > exitMs) stopRecording();
        }
        aboveSince = 0;
      }
    }, 80);
  }
  function stopVadLoop() {
    if (!vadTimer) return;
    clearInterval(vadTimer);
    vadTimer = null;
  }

  document.getElementById("voice-vad-toggle").addEventListener("change", async (e) => {
    if (e.target.checked) {
      try { await ensureStream(); } catch (_) { e.target.checked = false; return; }
      startWaveLoop();
      startVadLoop();
      setState("VAD активен", "ok");
    } else {
      stopVadLoop();
      stopWaveLoop();
      setState("ожидание");
    }
  });

  return () => {
    document.removeEventListener("keydown", onKeyDown);
    document.removeEventListener("keyup", onKeyUp);
    stopWaveLoop();
    stopVadLoop();
    unsub();
    if (recorder?.state === "recording") {
      try { recorder.stop(); } catch (_) {}
    }
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
  };
}

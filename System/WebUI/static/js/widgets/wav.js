// Convert a Blob (webm/ogg/opus from MediaRecorder) into a 16-bit mono WAV
// Blob suitable for POST /api/agent/asr/upload.
//
// AudioContext({ sampleRate }) forces the decoded buffer to the desired rate
// — Whisper expects 16 kHz, the orchestrator config matches.

export async function encodeWav(blob, targetRate = 16000) {
  const arrayBuf = await blob.arrayBuffer();
  const Ctx = window.AudioContext || window.webkitAudioContext;
  let ctx;
  try {
    ctx = new Ctx({ sampleRate: targetRate });
  } catch (_) {
    ctx = new Ctx(); // fallback if browser refuses non-default rate
  }
  const decoded = await ctx.decodeAudioData(arrayBuf);
  const samples = decoded.numberOfChannels === 1
    ? decoded.getChannelData(0)
    : mixToMono(decoded);
  const wav = float32ToWav(samples, decoded.sampleRate);
  ctx.close();
  return wav;
}

function mixToMono(audioBuffer) {
  const length = audioBuffer.length;
  const out = new Float32Array(length);
  for (let ch = 0; ch < audioBuffer.numberOfChannels; ch++) {
    const data = audioBuffer.getChannelData(ch);
    for (let i = 0; i < length; i++) out[i] += data[i];
  }
  for (let i = 0; i < length; i++) out[i] /= audioBuffer.numberOfChannels;
  return out;
}

function float32ToWav(samples, rate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  let offset = 0;
  function writeStr(s) { for (let i = 0; i < s.length; i++) view.setUint8(offset++, s.charCodeAt(i)); }
  function writeU32(v) { view.setUint32(offset, v, true); offset += 4; }
  function writeU16(v) { view.setUint16(offset, v, true); offset += 2; }
  writeStr("RIFF"); writeU32(36 + samples.length * 2); writeStr("WAVE");
  writeStr("fmt "); writeU32(16); writeU16(1); writeU16(1);
  writeU32(rate); writeU32(rate * 2); writeU16(2); writeU16(16);
  writeStr("data"); writeU32(samples.length * 2);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

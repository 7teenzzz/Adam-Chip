# Reference: Audio Module — I2S RX/TX Ring Buffers

## Microphone Input (I2S RX - INMP441)

**Community:** "Mic Audio Capture (I2S)" (37 nodes)

- **Hardware:** 2× INMP441 stereo microphones
- **I2S pins:** BCLK=48, WS=47, SD=21
- **Sample rate:** 16 kHz, Philips 32-bit format
- **Ring buffer:** 256 KB PSRAM (~4 seconds stereo audio)
- **Processing:** `convertRawSampleToPcm()` — convert to PCM 16-bit for Jetson

**Key functions:**
- `audioCaptureTask()` — FreeRTOS continuous capture task
- `applyAudioRuntimeUpdate()` — reconfigure gains dynamically
- `applyDcBlockFilter()` — remove DC offset
- `classifySignalState()` — detect silence/clipping

**Health monitoring:** `EspAudioHealthMonitor`
- Silence threshold: RMS < 24
- Clipping threshold: peak/RMS > 6.0
- Auto-restoration after 5 consecutive healthy polls

See `diploma/chapter-3/3.3.2_perception_motor_layers.md` for audio canal details.

---

## Speaker Output (I2S TX - PCM5102A + PAM8403)

**Community:** "Speaker Playback and Sounds" (16 nodes)

- **Hardware:** PCM5102A DAC + PAM8403 amplifier
- **I2S pins:** BCLK=38, LRCK=39, DATA=40
- **Format:** Mono 16-bit, 44.1 kHz
- **Ring buffer:** 32 KB DRAM (~372 ms audio)
- **Rate limiting:** 4 ms I2S drain backoff (prevents glitches on high load)

**Key functions:**
- `speakerPlaybackTask()` — FreeRTOS playback task
- `writeSpeakerData()` — DMA write to I2S TX FIFO
- `playSystemSound()` (12 edges) — boot/alert audio cues
- `beginSpeakerStream()` / `endSpeakerStream()` — HTTP audio streaming lifecycle

**System sounds:**
- Embedded WAV data in firmware (PROGMEM)
- Paths in `pathForSound()` enumeration
- Boot sound plays ~5.8s after initialization

See `diploma/chapter-3/3.3.2_perception_motor_layers.md` for audioflora details.

---

## Jetson Audio Streaming

**HTTP Speaker Endpoint:** POST `http://192.168.0.171:81/speaker`

- Jetson sends PCM frames (16-bit mono, 44.1 kHz) to this endpoint
- ESP32 buffers and plays immediately via I2S TX
- Separate from camera stream (port 81 multiplexed via separate HTTP server)

**Latency path:**
1. Jetson TTS synthesis (~2-3s for Silero)
2. HTTP POST to ESP32 (network latency ~5-50 ms)
3. Buffer fill + I2S DMA drain (~100-400 ms depending on frame size)
4. Speaker playback begins ~3-4s after TTS request

---

## Graphify Evidence

- Community "Mic Audio Capture (I2S)" — 37 nodes
- Community "Speaker Playback and Sounds" — 16 nodes (high cohesion 0.24)
- God-node: `recordMetricMs()` (11 edges)

See: `Knowledge-graphs/esp32/GRAPH_REPORT.md` (communities 11, 13)

#!/usr/bin/env python3
"""Direct ESP32 audio stream test: mono L-channel capture -> WAV playback.

Usage:
    python3 scripts/test_esp32_stream.py [duration_sec] [gain]

Examples:
    python3 scripts/test_esp32_stream.py          # 5s, current gain
    python3 scripts/test_esp32_stream.py 5 3.0    # 5s, gain=3.0
    python3 scripts/test_esp32_stream.py 10 1.5   # 10s, gain=1.5
"""
import json
import os
import struct
import sys
import time
import urllib.request
import wave
from datetime import datetime

ESP_BASE    = "http://192.168.0.171"
ESP_STREAM  = "http://192.168.0.171:81/audio"
ARTIFACTS   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "Subsystem", "AdamsServer", "artifacts", "mic_tests")
RATE        = 16000
FRAME_MS    = 20

DURATION_S  = int(sys.argv[1]) if len(sys.argv) > 1 else 5
TARGET_GAIN = float(sys.argv[2]) if len(sys.argv) > 2 else None

os.makedirs(ARTIFACTS, exist_ok=True)

# ── Query current audio state ────────────────────────────────────────────────
with urllib.request.urlopen(f"{ESP_BASE}/api/audio", timeout=5) as r:
    state = json.loads(r.read())
cap = state["capture"]
current_gain    = cap["software_gain"]
current_profile = cap["profile"]
print(f"ESP32 audio: profile={current_profile}  gain={current_gain}  "
      f"channels={cap['pcm_channels']}  clip_count={cap['clip_count']}")

# ── Apply gain if requested ──────────────────────────────────────────────────
if TARGET_GAIN is not None and TARGET_GAIN != current_gain:
    body = json.dumps({"software_gain": TARGET_GAIN}).encode()
    req = urllib.request.Request(f"{ESP_BASE}/api/audio", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as r:
        updated = json.loads(r.read())
    current_gain = updated["capture"]["software_gain"]
    print(f"Gain set to: {current_gain}")

# Switch to left-channel mono profile
TARGET_PROFILE = "inmp441_philips32_left"
if current_profile != TARGET_PROFILE:
    body = json.dumps({"profile": TARGET_PROFILE}).encode()
    req = urllib.request.Request(f"{ESP_BASE}/api/audio", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as r:
        updated = json.loads(r.read())
    current_profile = updated["capture"]["profile"]
    print(f"Profile set to: {current_profile}")

# ── Stream capture ───────────────────────────────────────────────────────────
frame_bytes  = RATE * 1 * 2 * FRAME_MS // 1000   # 640 bytes mono
total_frames = DURATION_S * 1000 // FRAME_MS

print(f"\nConnecting to {ESP_STREAM} ...")
resp = urllib.request.urlopen(ESP_STREAM, timeout=10)
hdr  = resp.read(44)
print(f"WAV header: {hdr[:4].decode('ascii', errors='replace')}  "
      f"size=0x{int.from_bytes(hdr[4:8], 'little'):08X}")

chunks: list[bytes] = []
print(f"Recording {DURATION_S}s ({total_frames} frames x {FRAME_MS}ms) ...")
t0 = time.perf_counter()

for i in range(total_frames):
    raw = resp.read(frame_bytes)
    if len(raw) < frame_bytes:
        print(f"  [!] Short read at frame {i}: {len(raw)} bytes")
        break
    chunks.append(raw)

elapsed = time.perf_counter() - t0
resp.close()

# ── Analysis ─────────────────────────────────────────────────────────────────
all_pcm = b"".join(chunks)
ms_vals = struct.unpack(f"<{len(all_pcm)//2}h", all_pcm)
rms        = int((sum(s * s for s in ms_vals) / len(ms_vals)) ** 0.5)
peak       = max(abs(s) for s in ms_vals)
clip_count = sum(1 for s in ms_vals if abs(s) >= 32700)
neg_pct    = sum(1 for s in ms_vals if s < 0) * 100 // len(ms_vals)
headroom_db = 20 * __import__("math").log10(32767 / peak) if peak > 0 else 99

print(f"\nResult:  frames={len(chunks)}  elapsed={elapsed:.2f}s")
print(f"Mono L:  RMS={rms}  peak={peak}  clips={clip_count}  neg={neg_pct}%  headroom={headroom_db:.1f}dB")
print(f"VAD:     threshold=400  -> {'VOICE DETECTED' if rms > 400 else 'silence'}")

# ── Save artifacts ────────────────────────────────────────────────────────────
ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
label = f"gain{current_gain:.1f}_{DURATION_S}s"

path_wav  = os.path.join(ARTIFACTS, f"{ts}_{label}_left.wav")
path_meta = os.path.join(ARTIFACTS, f"{ts}_{label}_meta.json")

with wave.open(path_wav, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
    w.writeframes(all_pcm)

meta = {
    "timestamp": ts,
    "profile": current_profile,
    "gain": current_gain,
    "duration_s": DURATION_S,
    "rate": RATE,
    "rms": rms,
    "peak": peak,
    "headroom_db": round(headroom_db, 1),
    "clip_count": clip_count,
    "neg_pct": neg_pct,
    "vad_threshold": 400,
}
with open(path_meta, "w") as f:
    json.dump(meta, f, indent=2)

print(f"\nSaved: {path_wav}")

print("\nOpening for playback ...")
if os.name == "nt":
    os.startfile(path_wav)
else:
    os.system(f"aplay {path_wav} &")

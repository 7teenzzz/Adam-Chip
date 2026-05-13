#!/usr/bin/env python3
"""
Standalone wake word diagnostic script.

Reads audio from mic via arecord, feeds 80ms chunks to OpenWakeWord,
and prints the raw score in real-time — no orchestrator required.

Usage:
    python3 scripts/test_wake_word.py [--device pulse] [--threshold 0.35]

Press Ctrl+C to stop.
"""
import argparse
import subprocess
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "data/wake_word/adam.onnx"

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 20          # one arecord read = 20ms
FRAMES_PER_CHUNK = 4   # 4 × 20ms = 80ms per OWW predict call

warnings.filterwarnings("ignore")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test OWW wake word detection")
    p.add_argument("--device", default="pulse", help="ALSA device (default: pulse)")
    p.add_argument("--threshold", type=float, default=0.35, help="Score threshold (default: 0.35)")
    p.add_argument("--debounce", type=int, default=3, help="Consecutive hits needed (default: 3)")
    p.add_argument("--vad", type=float, default=0.4, help="VAD threshold (default: 0.4)")
    p.add_argument("--model", default=str(MODEL_PATH), help="Path to .onnx model")
    return p.parse_args()


def load_oww(model_path: str, vad_threshold: float):
    import numpy as np
    import openwakeword

    print(f"Loading model: {model_path}", flush=True)
    oww = openwakeword.Model(
        wakeword_models=[model_path],
        inference_framework="onnx",
        vad_threshold=vad_threshold,
    )
    model_name = list(oww.models.keys())[0]
    print(f"Model name: {model_name}", flush=True)

    # flush initial ring buffer with silence (same as production code)
    silence = np.zeros(1280, dtype=np.int16)
    for _ in range(20):
        oww.predict(silence)

    return oww, model_name


def start_arecord(device: str, sample_rate: int, frame_ms: int) -> subprocess.Popen:
    frame_bytes = sample_rate * 2 * frame_ms // 1000  # 16-bit mono
    # -t raw: raw PCM, no WAV header — matches orchestrator exactly.
    # hw: devices are remapped to plughw: for format negotiation.
    capture_device = f"plughw:{device[3:]}" if device.startswith("hw:") else device
    cmd = [
        "arecord",
        "-q",
        "-D", capture_device,
        "-f", "S16_LE",
        "-r", str(sample_rate),
        "-c", "1",
        "-t", "raw",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main() -> None:
    args = parse_args()

    if not Path(args.model).exists():
        print(f"ERROR: model not found: {args.model}", file=sys.stderr)
        sys.exit(1)

    oww, model_name = load_oww(args.model, args.vad)

    import numpy as np

    frame_bytes = SAMPLE_RATE * 2 * FRAME_MS // 1000  # 640 bytes per 20ms frame
    consecutive = 0
    buf: list[bytes] = []

    print(f"\nDevice: {args.device} | threshold: {args.threshold} | debounce: {args.debounce} | vad: {args.vad}")
    print("Say 'адам' — watching for wake word...\n")
    print(f"{'TIME':8} {'SCORE':>8} {'HITS':>6}  BAR")
    print("-" * 50)

    proc = start_arecord(args.device, SAMPLE_RATE, FRAME_MS)

    try:
        while True:
            chunk = proc.stdout.read(frame_bytes)  # type: ignore[union-attr]
            if not chunk:
                print("arecord stopped (empty read)")
                break

            buf.append(chunk)
            if len(buf) < FRAMES_PER_CHUNK:
                continue

            pcm = b"".join(buf)
            buf.clear()

            audio = np.frombuffer(pcm, dtype=np.int16)
            prediction = oww.predict(audio)
            score = float(prediction.get(model_name, 0))

            if score >= args.threshold:
                consecutive += 1
            else:
                consecutive = 0

            triggered = consecutive >= args.debounce
            display_hits = consecutive
            if triggered:
                consecutive = 0  # reset after trigger

            # print every chunk (80ms), highlight when score > 0.1
            if score >= 0.1 or triggered:
                bar = "#" * int(score * 30)
                ts = time.strftime("%H:%M:%S")
                marker = " <<< WAKE!" if triggered else ""
                print(f"{ts} {score:8.3f} {display_hits:6d}  {bar}{marker}", flush=True)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    main()

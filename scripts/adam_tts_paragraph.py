#!/usr/bin/env python3
"""Play LongStoryShort.md through ESP32 speaker via Silero TTS.

Usage:
    python3 scripts/adam_tts_paragraph.py          # all paragraphs in sequence
    python3 scripts/adam_tts_paragraph.py 3        # only paragraph 3
    python3 scripts/adam_tts_paragraph.py 3 7      # paragraphs 3 to 7

Pipeline: /wav (24kHz WAV) → audioop resample 24k→44.1k → POST to ESP32 :82/speaker.
Flora: attentive during each paragraph, breathe after the last one.
No-proxy opener is used for ESP32 to bypass v2ray (CLAUDE.md gotcha).
"""
import audioop
import json
import struct
import sys
import time
import urllib.request
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

TTS_WAV_URL = "http://127.0.0.1:8082/wav"
ESP32_SPEAKER_URL = "http://10.10.10.171:82/speaker"
ORCHESTRATOR_URL = "http://127.0.0.1:8080"
SPEAKER = "eugene"
TTS_SAMPLE_RATE = 24000
ESP32_SAMPLE_RATE = 44100
TEXT_FILE = Path(__file__).parent.parent / "Agent-Adam-Chip/About/LongStoryShort.md"

# Bypasses v2ray proxy that intercepts ESP32 LAN traffic (CLAUDE.md gotcha).
_NO_PROXY = build_opener(ProxyHandler({}))


def load_paragraphs() -> list[str]:
    text = TEXT_FILE.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def speak_all(paragraphs: list[str]) -> None:
    """Synthesize and play paragraphs sequentially with flora animation.

    Flora rhythm: attentive (playback) → breathe (pause) → attentive (next) → …
    State is refreshed before every paragraph so long-running sessions can't drift.
    """
    try:
        for i, para in enumerate(paragraphs, 1):
            print(f"[{i}/{len(paragraphs)}] {para[:80]}{'…' if len(para) > 80 else ''}")
            wav_bytes = _synthesize(para)
            wav_44k = _resample_to_esp32(wav_bytes)
            _flora("attentive")          # refresh right before playback
            _post_to_esp32(wav_44k)
            if i < len(paragraphs):
                _flora("breathe")        # breathe during the pause
                time.sleep(1.7)
    finally:
        _flora("breathe")


def _flora(state: str) -> None:
    """Push a flora preset via the orchestrator API (non-blocking, best-effort)."""
    try:
        payload = json.dumps({"state": state}).encode()
        req = urllib.request.Request(
            f"{ORCHESTRATOR_URL}/api/flora/state",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
    except Exception as exc:
        print(f"flora {state}: {exc}", file=sys.stderr)


def _synthesize(text: str) -> bytes:
    payload = json.dumps({"text": text, "speaker": SPEAKER}).encode()
    req = urllib.request.Request(TTS_WAV_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _resample_to_esp32(wav_bytes: bytes) -> bytes:
    """Resample mono 16-bit 24kHz WAV from Silero to 44100 Hz for ESP32 PCM5102A."""
    # Silero output is always mono 16-bit — skip 44-byte standard header.
    pcm = wav_bytes[44:]
    pcm_44k, _ = audioop.ratecv(pcm, 2, 1, TTS_SAMPLE_RATE, ESP32_SAMPLE_RATE, None)
    # 60 ms silence tail prevents I2S pop on the MAX98357A when bit-clock stops.
    tail = b"\x00" * (ESP32_SAMPLE_RATE * 2 * 60 // 1000)
    pcm_44k += tail
    return _build_wav(pcm_44k, ESP32_SAMPLE_RATE)


def _build_wav(pcm: bytes, sample_rate: int) -> bytes:
    data_size = len(pcm)
    byte_rate = sample_rate * 2  # mono 16-bit
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, byte_rate, 2, 16,
        b"data", data_size,
    )
    return header + pcm


def _post_to_esp32(wav_bytes: bytes) -> None:
    req = urllib.request.Request(
        ESP32_SPEAKER_URL,
        data=wav_bytes,
        headers={"Content-Type": "audio/wav"},
    )
    duration_sec = len(wav_bytes) / (ESP32_SAMPLE_RATE * 2) + 5
    with _NO_PROXY.open(req, timeout=int(duration_sec)) as resp:
        body = resp.read().decode(errors="replace")
    print(f"ESP32: {body[:120]}")


def main() -> None:
    all_paragraphs = load_paragraphs()
    total = len(all_paragraphs)

    args = sys.argv[1:]

    if not args:
        selection = all_paragraphs
    elif len(args) == 1:
        try:
            n = int(args[0])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [start [end]]", file=sys.stderr)
            sys.exit(1)
        if n < 1 or n > total:
            print(f"Paragraph {n} not found (1–{total}).", file=sys.stderr)
            sys.exit(1)
        selection = [all_paragraphs[n - 1]]
    else:
        try:
            start, end = int(args[0]), int(args[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [start [end]]", file=sys.stderr)
            sys.exit(1)
        if start < 1 or end > total or start > end:
            print(f"Range {start}–{end} out of bounds (1–{total}).", file=sys.stderr)
            sys.exit(1)
        selection = all_paragraphs[start - 1:end]

    speak_all(selection)
    print("done.")


if __name__ == "__main__":
    main()

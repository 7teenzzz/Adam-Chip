#!/usr/bin/env python3
"""Diagnose stereo WAV artifacts: check L/R correlation, polarity, and downmix quality.

Compares the last saved stereo.wav with its mono counterpart to identify why
the mono downmix sounds bad while the stereo sounds fine.

Usage:
    python3 scripts/diagnose_stereo.py [path/to/stereo.wav]
    (if no path given, picks the most recent artifact)
"""
import glob
import math
import os
import struct
import sys
import wave

ARTIFACTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Subsystem", "AdamsServer", "artifacts", "mic_tests",
)


def load_stereo_channels(path: str):
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        sr = w.getframerate()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if ch != 2 or sw != 2:
        raise ValueError(f"Expected 16-bit stereo, got {ch}ch/{sw*8}bit")
    n = len(raw) // 4  # stereo int16 frames
    samples = struct.unpack(f"<{n*2}h", raw[:n*4])
    L = samples[0::2]
    R = samples[1::2]
    return L, R, sr


def rms(s):
    if not s:
        return 0
    return math.sqrt(sum(x * x for x in s) / len(s))


def peak(s):
    return max(abs(x) for x in s) if s else 0


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def correlation(a, b):
    """Pearson correlation coefficient between two sequences."""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    ma = sum(a[:n]) / n
    mb = sum(b[:n]) / n
    ca = [x - ma for x in a[:n]]
    cb = [x - mb for x in b[:n]]
    num = sum(x * y for x, y in zip(ca, cb))
    da = math.sqrt(sum(x * x for x in ca) or 1)
    db = math.sqrt(sum(x * x for x in cb) or 1)
    return num / (da * db)


def downmix(L, R):
    return tuple(L[i] // 2 + R[i] // 2 for i in range(min(len(L), len(R))))


def downmix_single(L, scale=1.0):
    return tuple(int(x * scale) for x in L)


def main():
    if len(sys.argv) > 1:
        stereo_path = sys.argv[1]
    else:
        files = sorted(glob.glob(os.path.join(ARTIFACTS, "*_stereo.wav")))
        if not files:
            print(f"No stereo artifacts found in {ARTIFACTS}")
            sys.exit(1)
        stereo_path = files[-1]
        print(f"Using most recent artifact: {os.path.basename(stereo_path)}\n")

    L, R, sr = load_stereo_channels(stereo_path)
    n = min(len(L), len(R))

    rms_L = rms(L)
    rms_R = rms(R)
    pk_L  = peak(L)
    pk_R  = peak(R)
    corr_LR = correlation(L, R)

    print("=" * 60)
    print(f"File        : {os.path.basename(stereo_path)}")
    print(f"Samples     : {n} per channel @ {sr} Hz = {n/sr:.2f}s")
    print("=" * 60)
    print(f"\n[L channel]  RMS={rms_L:.1f}  peak={pk_L}")
    print(f"[R channel]  RMS={rms_R:.1f}  peak={pk_R}")
    print(f"\n[Correlation L vs R]: {corr_LR:+.4f}")
    if abs(corr_LR) < 0.05:
        verdict = "INDEPENDENT (one mic may be silent)"
    elif corr_LR > 0.7:
        verdict = "IN PHASE — downmix should work well"
    elif corr_LR > 0.3:
        verdict = "WEAKLY CORRELATED (spacing / timing delay)"
    elif corr_LR < -0.7:
        verdict = "PHASE INVERTED — (L+R)/2 will CANCEL SIGNAL ← likely culprit"
    elif corr_LR < -0.3:
        verdict = "PARTIALLY OUT OF PHASE — partial cancellation in downmix"
    else:
        verdict = "LOW CORRELATION"
    print(f"  Verdict: {verdict}")

    # Compare downmix variants
    mix_avg   = downmix(L, R)          # current: (L//2 + R//2)
    mix_L     = downmix_single(L)      # mono from L only
    mix_R     = downmix_single(R)      # mono from R only
    mix_sub   = tuple(L[i] // 2 - R[i] // 2 for i in range(n))  # (L-R)/2

    print("\n[Downmix comparison] (RMS / peak)")
    print(f"  (L+R)/2  (current)  : RMS={rms(mix_avg):.1f}  peak={peak(mix_avg)}")
    print(f"  L only              : RMS={rms(mix_L):.1f}  peak={peak(mix_L)}")
    print(f"  R only              : RMS={rms(mix_R):.1f}  peak={peak(mix_R)}")
    print(f"  (L-R)/2  (polarity fix): RMS={rms(mix_sub):.1f}  peak={peak(mix_sub)}")

    # Detect if one channel is silent / very weak
    if rms_L < 10:
        print("\n  [!] L channel appears SILENT — mic not connected or LR pin wrong")
    if rms_R < 10:
        print("\n  [!] R channel appears SILENT — mic not connected or LR pin wrong")
    if rms_L > 0 and rms_R > 0:
        ratio = rms_L / rms_R
        if ratio > 4 or ratio < 0.25:
            print(f"\n  [!] L/R RMS ratio = {ratio:.2f} — one mic is much weaker than the other")

    # Check for clipping (half-wave rectification symptom)
    neg_L = sum(1 for x in L if x < 0)
    neg_R = sum(1 for x in R if x < 0)
    print(f"\n[Polarity check] negative samples: L={neg_L}/{n} ({100*neg_L/n:.1f}%)  R={neg_R}/{n} ({100*neg_R/n:.1f}%)")
    if neg_L / n < 0.05:
        print("  [!] L channel: almost NO negative samples → half-wave rectification (Philips shift bug)")
    if neg_R / n < 0.05:
        print("  [!] R channel: almost NO negative samples → half-wave rectification (Philips shift bug)")

    print("\n[Recommendation]")
    if neg_L / n < 0.05 or neg_R / n < 0.05:
        print("  Switch profile to 'inmp441_msb32_stereo' — MSB format preserves sign bit correctly")
        print("  OR use 'inmp441_msb32_left'/'right' for single-mic mono")
    elif corr_LR < -0.5:
        print("  Mics are phase-inverted: use (L-R)/2 downmix OR invert one mic physically")
        print("  Quick fix in test script: change downmix to samples[j]//2 - samples[j+1]//2")
    elif abs(rms_L - rms_R) / max(rms_L, rms_R, 1) > 0.5:
        print("  One mic is much weaker — check wiring / LR pin / mic orientation")
        stronger = "L" if rms_L > rms_R else "R"
        slot = 1 if stronger == "L" else 2
        print(f"  Temporary fix: use only the {stronger} channel (preferredSlot={slot})")
    else:
        print("  Channels look correlated and in-phase — downmix should work.")
        print("  Investigate streaming alignment or bit-depth issues.")

    print()


if __name__ == "__main__":
    main()

"""TTS audio DSP chain (Phase 29 — ESP Audio Output).

Applied to the Silero TTS WAV before playback / ESP32 send, to make Adam's
voice louder and cleaner on the low-power MAX98357A speakers (3 W, 200 Hz–
20 kHz, 4 Ω) without clipping.

Stage A (this module, enabled by default):
    high-pass ~180 Hz  →  fixed makeup gain  →  brickwall limiter (−1 dBFS)
  - HPF drops sub-200 Hz energy the speakers cannot reproduce, freeing amp
    headroom and stopping cone flap.
  - Fixed makeup gain (NOT per-utterance normalisation — see Phase 29 D-06):
    every utterance gets the same dB, so relative dynamics and inter-sentence
    consistency are preserved (no pumping).
  - Brickwall limiter guarantees |sample| ≤ ceiling → zero clipping, replacing
    the old hard-clip in Orchestrator._apply_wav_volume.

Stage B (added later): soft-knee compressor + presence EQ.

**Fail-safe contract:** every public function returns the input WAV/PCM
unchanged on ANY error (bad header, missing deps, filter failure). TTS must
never go silent because of a DSP bug.
"""

from __future__ import annotations

import struct

__all__ = ["process_tts_wav", "resample_pcm16_soxr"]


def _db_to_lin(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _find_data_chunk(wav: bytes) -> tuple[int, int, int, int] | None:
    """Return (pcm_start, pcm_end, sample_rate, channels) for a 16-bit PCM WAV.

    Returns None if the WAV is malformed or not 16-bit PCM.
    """
    if not wav or len(wav) < 44:
        return None
    if wav[0:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return None
    try:
        # fmt: audio_format(2) channels(2) sample_rate(4) ... bits(2 @ offset 34)
        channels = struct.unpack_from("<H", wav, 22)[0]
        sample_rate = struct.unpack_from("<I", wav, 24)[0]
        bits = struct.unpack_from("<H", wav, 34)[0]
        if bits != 16 or channels not in (1, 2):
            return None
        data_marker = wav.find(b"data", 12, min(len(wav), 4096))
        if data_marker < 0 or data_marker + 8 > len(wav):
            return None
        pcm_size = struct.unpack_from("<I", wav, data_marker + 4)[0]
        pcm_start = data_marker + 8
        pcm_end = min(pcm_start + pcm_size, len(wav))
        if pcm_end <= pcm_start:
            return None
        return pcm_start, pcm_end, sample_rate, channels
    except Exception:
        return None


def _compress_mono(x, sr, threshold_db, ratio, attack_ms, release_ms, knee_db):
    """Soft-knee feed-forward compressor (Phase 29 Stage B), mono float in/out.

    Gentle voice compression: pulls down levels above threshold so the makeup
    gain can raise overall loudness without the limiter slamming every peak.
    Gain-reduction is smoothed with a single release-time pole (vectorised via
    lfilter) — slow-ish attack is fine here because the brickwall limiter
    downstream is the hard ceiling. Returns input unchanged on any error.
    """
    if ratio is None or ratio <= 1.0:
        return x
    try:
        import numpy as np
        from scipy.signal import lfilter

        eps = 1e-9
        level_db = 20.0 * np.log10(np.abs(x) + eps)
        over = level_db - float(threshold_db)
        slope = (1.0 / float(ratio)) - 1.0  # negative
        gr = np.zeros_like(level_db)
        k = float(knee_db)
        if k > 0:
            lo, hi = -k / 2.0, k / 2.0
            in_knee = (over > lo) & (over <= hi)
            above = over > hi
            gr[in_knee] = slope * (over[in_knee] - lo) ** 2 / (2.0 * k)
            gr[above] = slope * over[above]
        else:
            above = over > 0
            gr[above] = slope * over[above]
        tau = max(float(release_ms), 1.0) / 1000.0
        a = float(np.exp(-1.0 / (max(sr, 1) * tau)))
        gr_smooth = lfilter([1.0 - a], [1.0, -a], gr).astype(np.float32)
        gain = np.power(10.0, gr_smooth / 20.0).astype(np.float32)
        return (x * gain).astype(np.float32)
    except Exception:
        return x


def _presence_eq_mono(x, sr, f0, gain_db, q):
    """RBJ peaking-EQ boost around f0 (Phase 29 Stage B), mono float in/out.

    Lifts speech presence (~3 kHz) for intelligibility on small speakers.
    Returns input unchanged on any error or near-zero gain.
    """
    try:
        import numpy as np
        from scipy.signal import lfilter

        if abs(float(gain_db)) < 0.05 or f0 <= 0 or f0 >= sr * 0.5:
            return x
        A = 10.0 ** (float(gain_db) / 40.0)
        w0 = 2.0 * np.pi * float(f0) / sr
        cw, sw = np.cos(w0), np.sin(w0)
        alpha = sw / (2.0 * max(float(q), 1e-3))
        b = np.array([1 + alpha * A, -2 * cw, 1 - alpha * A], dtype=np.float64)
        a = np.array([1 + alpha / A, -2 * cw, 1 - alpha / A], dtype=np.float64)
        return lfilter(b / a[0], a / a[0], x).astype(np.float32)
    except Exception:
        return x


def process_tts_wav(
    wav: bytes,
    *,
    enabled: bool = True,
    hpf_hz: float = 180.0,
    makeup_db: float = 3.0,
    limiter_ceiling_dbfs: float = -1.0,
    volume: float = 1.0,
    comp_enabled: bool = False,
    comp_threshold_dbfs: float = -18.0,
    comp_ratio: float = 2.0,
    comp_attack_ms: float = 10.0,
    comp_release_ms: float = 120.0,
    comp_knee_db: float = 6.0,
    presence_enabled: bool = False,
    presence_hz: float = 3000.0,
    presence_db: float = 2.5,
    presence_q: float = 0.9,
) -> bytes:
    """Apply the Stage-A DSP chain to a 16-bit PCM WAV, preserving the header.

    Chain: HPF(hpf_hz) → [Stage B: compressor → presence EQ] → gain(makeup_db
    + volume) → brickwall limiter(ceiling). Stage B stages are opt-in via
    comp_enabled / presence_enabled (off by default = pure Stage A).

    The ``volume`` (tuning.voice.volume) folds into the makeup as an extra
    linear multiplier, so the existing UI volume slider keeps working — but
    the limiter now guarantees no clipping regardless of how loud volume is set.

    Returns the input unchanged on any error or when disabled.
    """
    if not wav:
        return wav

    parsed = _find_data_chunk(wav)
    if parsed is None:
        return wav
    pcm_start, pcm_end, sample_rate, channels = parsed

    gain_lin = _db_to_lin(makeup_db) * (float(volume) if volume is not None else 1.0)
    ceiling = _db_to_lin(limiter_ceiling_dbfs)

    # Fast path: nothing to do (disabled, unity gain, no HPF).
    if not enabled and abs(gain_lin - 1.0) < 0.005:
        return wav

    try:
        import numpy as np

        pcm = wav[pcm_start:pcm_end]
        # Trim to whole frames (channels * 2 bytes).
        frame_bytes = 2 * channels
        usable = (len(pcm) // frame_bytes) * frame_bytes
        if usable <= 0:
            return wav
        samples = np.frombuffer(pcm[:usable], dtype="<i2").astype(np.float32) / 32768.0

        if enabled and hpf_hz and hpf_hz > 0 and sample_rate > 0:
            nyq = sample_rate * 0.5
            if 0 < hpf_hz < nyq:
                try:
                    from scipy.signal import butter, sosfilt

                    sos = butter(2, hpf_hz / nyq, btype="highpass", output="sos")
                    if channels == 2:
                        view = samples.reshape(-1, 2)
                        view[:, 0] = sosfilt(sos, view[:, 0])
                        view[:, 1] = sosfilt(sos, view[:, 1])
                        samples = view.reshape(-1)
                    else:
                        samples = sosfilt(sos, samples).astype(np.float32)
                except Exception:
                    pass  # HPF optional — keep going without it

        # Stage B: soft-knee compressor → presence EQ (after HPF, before gain).
        if enabled and (comp_enabled or presence_enabled):
            def _stageb(mono):
                if comp_enabled:
                    mono = _compress_mono(
                        mono, sample_rate, comp_threshold_dbfs, comp_ratio,
                        comp_attack_ms, comp_release_ms, comp_knee_db)
                if presence_enabled:
                    mono = _presence_eq_mono(
                        mono, sample_rate, presence_hz, presence_db, presence_q)
                return mono

            if channels == 2:
                view = samples.reshape(-1, 2)
                view[:, 0] = _stageb(view[:, 0])
                view[:, 1] = _stageb(view[:, 1])
                samples = view.reshape(-1)
            else:
                samples = _stageb(samples)

        if abs(gain_lin - 1.0) >= 0.005:
            samples = samples * gain_lin

        # Brickwall limiter — guarantee no clipping. Not per-utterance
        # normalisation: only samples exceeding the ceiling are affected.
        np.clip(samples, -ceiling, ceiling, out=samples)

        # Short fade in/out (~5 ms) to kill the filter start-up transient
        # (HPF/compressor/EQ start from zero state → a click at phrase onset)
        # and the DAC edge click at the end. Cheap and inaudible on speech.
        try:
            fade = int(sample_rate * 0.012)
            if fade > 1 and samples.size >= fade * channels * 2:
                ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
                if channels == 2:
                    v = samples.reshape(-1, 2)
                    v[:fade, 0] *= ramp; v[:fade, 1] *= ramp
                    v[-fade:, 0] *= ramp[::-1]; v[-fade:, 1] *= ramp[::-1]
                    samples = v.reshape(-1)
                else:
                    samples[:fade] *= ramp
                    samples[-fade:] *= ramp[::-1]
        except Exception:
            pass

        out_i16 = np.round(samples * 32768.0).astype(np.int32)
        np.clip(out_i16, -32768, 32767, out=out_i16)
        out_bytes = out_i16.astype("<i2").tobytes()

        out = bytearray(wav)
        out[pcm_start:pcm_start + len(out_bytes)] = out_bytes
        return bytes(out)
    except Exception:
        return wav


def resample_pcm16_soxr(pcm: bytes, channels: int, in_sr: int, out_sr: int) -> bytes:
    """High-quality resample of raw 16-bit PCM via soxr (replaces audioop.ratecv).

    Returns the input unchanged on any error or when rates already match.
    """
    if not pcm or in_sr == out_sr or in_sr <= 0 or out_sr <= 0:
        return pcm
    try:
        import numpy as np
        import soxr

        frame_bytes = 2 * max(1, channels)
        usable = (len(pcm) // frame_bytes) * frame_bytes
        if usable <= 0:
            return pcm
        arr = np.frombuffer(pcm[:usable], dtype="<i2")
        if channels == 2:
            arr = arr.reshape(-1, 2)
        out = soxr.resample(arr, in_sr, out_sr)  # float/int in → same dtype family
        out_i16 = np.clip(np.round(out), -32768, 32767).astype("<i2")
        return out_i16.tobytes()
    except Exception:
        return pcm

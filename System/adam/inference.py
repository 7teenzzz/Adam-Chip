from __future__ import annotations

import asyncio
import audioop
import base64
import io
import json
import re
import struct
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, urlopen, ProxyHandler

# Bypass system HTTP proxy for ESP32 LAN traffic (v2ray on this Jetson hijacks
# urllib via env vars and leaks sockets back to ESP32:81 port pool of 4).
_NO_PROXY_OPENER = build_opener(ProxyHandler({}))


# ESP32 PCM5102A speaker contract (Subsystem/AdamsServer/config/AdamsConfig.h:91 →
# kSpeakerSampleRate). The /speaker endpoint validates WAV header and rejects
# anything that is not mono / 16-bit / 44100 Hz with HTTP 400.
ESP32_SPEAKER_SAMPLE_RATE = 44100
ESP32_SPEAKER_CHANNELS = 1
ESP32_SPEAKER_BITS = 16


def _build_wav_header(pcm_size: int, sample_rate: int, channels: int, bits: int) -> bytes:
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    chunk_size = 36 + pcm_size
    return (
        b"RIFF" + struct.pack("<I", chunk_size) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
        + b"data" + struct.pack("<I", pcm_size)
    )


def _parse_wav(wav_bytes: bytes) -> tuple[int, int, int, int, int, int]:
    """Walk RIFF/WAVE chunks and return (audio_format, channels, sample_rate, bits, data_off, data_size).

    The minimal 44-byte WAV layout (RIFF + fmt + data) is just one valid form.
    Real-world WAVs may interleave LIST/INFO/bext/cue/JUNK chunks between fmt
    and data, so a fixed offset 44 is fragile. This walker locates the data
    chunk regardless of preamble layout.
    """
    if len(wav_bytes) < 12 or wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise ValueError("invalid WAV header")
    audio_format = channels = sample_rate = bits = 0
    pos = 12
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos:pos + 4]
        chunk_size = struct.unpack_from("<I", wav_bytes, pos + 4)[0]
        body = pos + 8
        if chunk_id == b"fmt ":
            if chunk_size < 16 or body + 16 > len(wav_bytes):
                raise ValueError("truncated fmt chunk")
            audio_format = struct.unpack_from("<H", wav_bytes, body)[0]
            channels = struct.unpack_from("<H", wav_bytes, body + 2)[0]
            sample_rate = struct.unpack_from("<I", wav_bytes, body + 4)[0]
            bits = struct.unpack_from("<H", wav_bytes, body + 14)[0]
        elif chunk_id == b"data":
            if audio_format == 0:
                raise ValueError("data chunk before fmt chunk")
            data_size = min(chunk_size, len(wav_bytes) - body)
            return audio_format, channels, sample_rate, bits, body, data_size
        # Chunks are padded to even length per RIFF spec.
        pos = body + chunk_size + (chunk_size & 1)
    raise ValueError("no data chunk found")


def _prepare_wav_for_esp32_speaker(wav_bytes: bytes) -> bytes:
    """Convert arbitrary 16-bit PCM WAV to ESP32 contract: mono / 16-bit / 44100 Hz.

    Validates the source header, downmixes stereo→mono if needed, resamples to
    44100 Hz via audioop.ratecv, and rebuilds a minimal 44-byte WAV header.
    """
    audio_format, channels, sample_rate, bits, data_off, data_size = _parse_wav(wav_bytes)
    if audio_format != 1 or bits != ESP32_SPEAKER_BITS:
        raise ValueError(f"unsupported PCM format={audio_format} bits={bits}")
    if channels not in (1, 2):
        raise ValueError(f"unsupported channels={channels}")
    pcm = wav_bytes[data_off:data_off + data_size]
    if channels == 2:
        pcm = audioop.tomono(pcm, 2, 0.5, 0.5)
    if sample_rate != ESP32_SPEAKER_SAMPLE_RATE:
        pcm, _state = audioop.ratecv(pcm, 2, 1, sample_rate, ESP32_SPEAKER_SAMPLE_RATE, None)
    return _build_wav_header(len(pcm), ESP32_SPEAKER_SAMPLE_RATE,
                             ESP32_SPEAKER_CHANNELS, ESP32_SPEAKER_BITS) + pcm


@dataclass
class ServiceHealth:
    ok: bool
    detail: str
    loading: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "detail": self.detail, "loading": self.loading}


class OpenAIChatClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "http://127.0.0.1:8081/v1")).rstrip("/")
        self.model = str(config.get("model", "qwen3-4b-quantized"))
        self.timeout = float(config.get("timeout_sec", 30))
        self.temperature = float(config.get("temperature", 0.7))
        self.max_tokens = int(config.get("max_tokens", 220))
        # Disable chain-of-thought thinking for models that support it (e.g. Gemma 4).
        # Thinking consumes all max_tokens before producing a reply, leaving content empty.
        self.disable_thinking = bool(config.get("disable_thinking", True))

    async def generate(self, messages: list[dict[str, str]]) -> str:
        return await asyncio.to_thread(self._generate_sync, messages)

    async def generate_streaming(  # AsyncGenerator[str, None]
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ):
        import httpx  # lazy — only needed for streaming path
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": True,
            "cache_prompt": True,  # llama-server: reuse KV cache across requests with same prefix
        }
        if self.disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            async with client.stream(
                "POST",
                self.base_url + "/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                        content = (data.get("choices", [{}])[0].get("delta", {}).get("content") or "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, IndexError, KeyError):
                        pass

    async def health(self) -> ServiceHealth:
        return await asyncio.to_thread(self._health_sync)

    def _generate_sync(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "cache_prompt": True,
        }
        if self.disable_thinking:
            # Disable chain-of-thought for Gemma 4 and similar thinking models.
            # Prefer --reasoning off at the llama-server level (adam-llm.service);
            # this flag is a fallback for servers that support the API parameter.
            payload["thinking"] = {"type": "disabled"}
        raw = self._post("/chat/completions", payload)
        choices = raw.get("choices", [])
        if not choices:
            raise RuntimeError("llm returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        return str(content).strip()

    def _health_sync(self) -> ServiceHealth:
        try:
            req = Request(self.base_url + "/models", method="GET")
            with urlopen(req, timeout=2) as resp:
                return ServiceHealth(resp.status < 500, f"HTTP {resp.status}")
        except HTTPError as exc:
            return ServiceHealth(False, f"HTTP {exc.code}", loading=exc.code == 503)
        except (URLError, OSError) as exc:
            return ServiceHealth(False, str(exc))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = Request(self.base_url + path, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


def create_llm_client(config: dict[str, Any]) -> OpenAIChatClient:
    return OpenAIChatClient(config)


_VALID_TTS_OUTPUT_TARGETS = ("jetson_hdmi", "esp32_speaker")


class TTSClient:
    def __init__(self, config: dict[str, Any], mcu_speaker_url: str | None = None) -> None:
        self.base_url = str(config.get("base_url", "http://127.0.0.1:8082")).rstrip("/")
        self.timeout = float(config.get("timeout_sec", 20))
        self.speaker = str(config.get("speaker", "eugene"))
        self.output_device = str(config.get("output_device", "")).strip()
        target = str(config.get("output_target", "jetson_hdmi")).strip() or "jetson_hdmi"
        if target not in _VALID_TTS_OUTPUT_TARGETS:
            # Schema enum is documentation-only — nothing enforces the value at
            # runtime. Log loudly and degrade to local playback rather than
            # silently routing audio through whichever branch matches the typo.
            import logging as _logging
            _logging.getLogger("adam.tts").warning(
                "Unknown TTS output_target=%r; falling back to 'jetson_hdmi'. Valid: %s",
                target, _VALID_TTS_OUTPUT_TARGETS,
            )
            target = "jetson_hdmi"
        self.output_target = target
        # mcu_speaker_url is required only when output_target='esp32_speaker'.
        # Stored regardless so a later runtime config swap can flip the target.
        self._mcu_speaker_url = (mcu_speaker_url or "").strip() or None
        self._current_play_proc: Any = None  # active aplay Popen handle for barge-in interrupt
        self._session: Any = None
        # Hook for orchestrator to log barge-in attempts that cannot stop ESP32 audio.
        self._barge_in_event_emitter: Any = None

    def _get_session(self) -> Any:
        if self._session is None or self._session.is_closed:
            import httpx
            self._session = httpx.Client(base_url=self.base_url, timeout=self.timeout, trust_env=False)
        return self._session

    async def speak(self, text: str) -> dict[str, Any]:
        chunks = [chunk for chunk in split_sentences(text) if chunk.strip()]
        results: list[dict[str, Any]] = []
        for chunk in chunks:
            results.append(await asyncio.to_thread(self._synthesize_sync, chunk))
        ok = all(bool(result.get("ok")) for result in results) if results else True
        return {"ok": ok, "degraded": not ok, "chunks": len(chunks), "results": results}

    async def health(self) -> ServiceHealth:
        return await asyncio.to_thread(self._health_sync)

    def _synthesize_sync(self, text: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"text": text, "speaker": self.speaker}
        if self.output_device:
            payload["output_device"] = self.output_device
        try:
            resp = self._get_session().post("/speak", json=payload)
            body = self._decode(resp.text)
            playback = body.get("playback", {}) if isinstance(body.get("playback"), dict) else {}
            playback_ok = bool(playback.get("ok", True)) if playback.get("enabled", True) else True
            body_ok = bool(body.get("ok", True))
            return {"ok": resp.status_code < 500 and body_ok and playback_ok, "status": resp.status_code, "body": body}
        except Exception as exc:
            return {"ok": False, "status": 0, "error": str(exc), "text": text}

    def _get_wav_bytes_sync(self, text: str) -> bytes | None:
        """Synthesize text and return raw WAV bytes without triggering playback."""
        payload: dict[str, Any] = {"text": text, "speaker": self.speaker}
        try:
            resp = self._get_session().post("/wav", json=payload)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    def _play_wav_bytes_sync(self, wav_bytes: bytes) -> dict[str, Any]:
        """Route WAV playback to the configured output target. Blocks until done."""
        if self.output_target == "esp32_speaker":
            return self._play_wav_bytes_to_esp32_sync(wav_bytes)
        return self._play_wav_bytes_local_sync(wav_bytes)

    def _play_wav_bytes_local_sync(self, wav_bytes: bytes) -> dict[str, Any]:
        """Play WAV bytes via local ALSA/PulseAudio. Blocks until playback completes.

        Uses Popen (not subprocess.run) so that interrupt_playback() can kill
        the process mid-playback for barge-in support.

        Try order: paplay (PulseAudio) → aplay <device> → aplay default.
        """
        import shutil
        import subprocess
        import tempfile
        import os
        dev = self.output_device or "default"
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                wav_path = f.name
        except OSError as exc:
            return {"ok": False, "error": f"tempfile: {exc}"}

        def _candidates() -> list[list[str]]:
            # Prefer explicit ALSA device (reliable for HDMI output).
            # Fall back to default ALSA, then PulseAudio default sink.
            cmds: list[list[str]] = []
            if ap := shutil.which("aplay"):
                cmds.append([ap, "-q", "-D", dev, wav_path])
                if dev != "default":
                    cmds.append([ap, "-q", "-D", "default", wav_path])
            if pp := shutil.which("paplay"):
                cmds.append([pp, wav_path])
            return cmds

        candidates = _candidates()
        if not candidates:
            try:
                os.unlink(wav_path)
            except OSError:
                pass
            return {"ok": False, "error": "no audio player found"}

        last_rc = -1
        try:
            for cmd in candidates:
                self._current_play_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                last_rc = self._current_play_proc.wait()
                self._current_play_proc = None
                if last_rc == 0:
                    return {"ok": True, "returncode": 0, "player": cmd[0]}
            return {"ok": False, "returncode": last_rc, "player": candidates[-1][0]}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            self._current_play_proc = None
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def _play_wav_bytes_to_esp32_sync(self, wav_bytes: bytes) -> dict[str, Any]:
        """POST WAV to ESP32 PCM5102A speaker (port 81), then wait for playback to finish.

        Silero v5_5_ru produces 24000 Hz mono; ESP32 firmware enforces mono /
        16-bit / 44100 Hz and rejects mismatched headers with HTTP 400. We
        resample on Jetson via audioop.ratecv before POST. No fallback to local
        playback on error — failed POST returns ok=False so upstream sees the
        TTS chunk as degraded.

        ESP-IDF's HTTP server returns the response as soon as the request body
        is consumed by the handler — which writes into the I2S ring buffer but
        does NOT wait for the DAC to drain. Without compensation, callers think
        playback is done while audio is still streaming out of PCM5102A, and
        the reply window starts ticking too early. We sleep for the prepared
        PCM duration after POST returns to align "TTS finished" with reality.
        """
        if not self._mcu_speaker_url:
            return {"ok": False, "error": "mcu_speaker_url not configured", "target": "esp32_speaker"}
        try:
            prepared = _prepare_wav_for_esp32_speaker(wav_bytes)
        except ValueError as exc:
            return {"ok": False, "error": f"wav prep: {exc}", "target": "esp32_speaker"}
        # PCM bytes after the 44-byte header we built ourselves: prepared starts
        # with WavHeader so subtract its size, then divide by bytes/sec.
        pcm_bytes = max(0, len(prepared) - 44)
        bytes_per_sec = ESP32_SPEAKER_SAMPLE_RATE * ESP32_SPEAKER_CHANNELS * (ESP32_SPEAKER_BITS // 8)
        duration_sec = pcm_bytes / bytes_per_sec if bytes_per_sec else 0.0
        # Allow timeout to cover at least the playback duration plus a margin
        # for the network round-trip and ESP32 buffer ramp-up.
        post_timeout = max(self.timeout, duration_sec + 5.0)
        req = Request(self._mcu_speaker_url, data=prepared, method="POST")
        req.add_header("Content-Type", "audio/wav")
        t0 = time.perf_counter()
        try:
            # Bypass system proxy — env HTTP proxy (v2ray) hijacks LAN traffic
            # and leaks sockets to ESP32:81, blocking subsequent connects.
            with _NO_PROXY_OPENER.open(req, timeout=post_timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                ok = resp.status < 400
        except HTTPError as exc:
            return {
                "ok": False, "status": exc.code, "error": f"HTTP {exc.code}",
                "target": "esp32_speaker",
            }
        except (URLError, OSError) as exc:
            return {"ok": False, "error": str(exc), "target": "esp32_speaker"}
        # Block remaining playback time so caller-visible "TTS finished" matches
        # actual audio end — within the bytes already buffered in I2S DMA.
        elapsed = time.perf_counter() - t0
        wait_extra = duration_sec - elapsed
        if wait_extra > 0:
            time.sleep(min(wait_extra, duration_sec))
        return {
            "ok": ok, "status": resp.status, "body": body, "target": "esp32_speaker",
            "duration_sec": round(duration_sec, 3),
            "post_sec": round(elapsed, 3),
        }

    def interrupt_playback(self) -> None:
        """Kill the active aplay process (barge-in). Safe to call from any thread.

        Limitation: when output_target='esp32_speaker' there is no analogous
        kill — the ESP32 firmware does not currently expose a stop endpoint, so
        any audio already POSTed will keep playing through the I2S buffer until
        it drains. The emitter hook lets the orchestrator surface the gap so
        operators can see why barge-in didn't take effect on ESP32.
        """
        proc = self._current_play_proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=0.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._current_play_proc = None
        if self.output_target == "esp32_speaker" and self._barge_in_event_emitter is not None:
            try:
                self._barge_in_event_emitter("tts_barge_in_unsupported", {"target": "esp32_speaker"})
            except Exception:
                pass

    def _health_sync(self) -> ServiceHealth:
        try:
            req = Request(self.base_url + "/health", method="GET")
            with urlopen(req, timeout=2) as resp:
                return ServiceHealth(resp.status < 500, f"HTTP {resp.status}")
        except HTTPError as exc:
            return ServiceHealth(False, f"HTTP {exc.code}", loading=exc.code == 503)
        except (URLError, OSError) as exc:
            return ServiceHealth(False, str(exc))

    @staticmethod
    def _decode(raw: str) -> dict[str, Any]:
        try:
            decoded = json.loads(raw)
            return decoded if isinstance(decoded, dict) else {"value": decoded}
        except json.JSONDecodeError:
            return {"raw": raw}



class WhisperASRClient:
    """HTTP client for a Whisper-compatible ASR microservice (POST /transcribe → {"transcript": "..."})."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "http://127.0.0.1:8095")).rstrip("/")
        self.sample_rate = int(config.get("sample_rate", 16000))
        self.timeout = float(config.get("timeout_sec", 30))
        self._session: Any = None

    def _get_session(self) -> Any:
        if self._session is None or self._session.is_closed:
            import httpx
            self._session = httpx.Client(base_url=self.base_url, timeout=self.timeout, trust_env=False)
        return self._session

    async def health(self) -> ServiceHealth:
        return await asyncio.to_thread(self._health_sync)

    def _health_sync(self) -> ServiceHealth:
        try:
            req = Request(self.base_url + "/health", method="GET")
            with urlopen(req, timeout=2) as resp:
                return ServiceHealth(resp.status < 500, f"HTTP {resp.status}")
        except HTTPError as exc:
            return ServiceHealth(False, f"HTTP {exc.code}", loading=exc.code == 503)
        except (URLError, OSError) as exc:
            return ServiceHealth(False, str(exc))

    async def transcribe_pcm(self, pcm: bytes) -> str:
        return await asyncio.to_thread(self._transcribe_pcm_sync, pcm)

    def _transcribe_pcm_sync(self, pcm: bytes) -> str:
        if not pcm:
            return ""
        wav_bytes = self._pcm_to_wav(pcm)
        try:
            resp = self._get_session().post("/transcribe", content=wav_bytes, headers={"Content-Type": "audio/wav"})
            resp.raise_for_status()
            return str(resp.json().get("transcript", "")).strip()
        except Exception:
            req = Request(self.base_url + "/transcribe", data=wav_bytes, method="POST")
            req.add_header("Content-Type", "audio/wav")
            with urlopen(req, timeout=self.timeout) as resp_u:
                raw = json.loads(resp_u.read().decode("utf-8"))
            return str(raw.get("transcript", "")).strip()

    def _pcm_to_wav(self, pcm: bytes) -> bytes:
        out = io.BytesIO()
        with wave.open(out, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            handle.writeframes(pcm)
        return out.getvalue()


class WhisperXASRClient(WhisperASRClient):
    """HTTP client for ASR_WhisperX.py microservice (whisperx + CUDA).

    API contract is identical to WhisperASRClient: POST /transcribe with WAV body,
    returns {"transcript": "..."}. This subclass exists to distinguish the provider
    in health checks and logs.
    """

    def _health_sync(self) -> ServiceHealth:
        try:
            req = Request(self.base_url + "/health", method="GET")
            with urlopen(req, timeout=3) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                ok = bool(body.get("ok", False))
                model_loaded = bool(body.get("model_loaded", False))
                detail = f"whisperx {'loaded' if model_loaded else 'loading'}"
                return ServiceHealth(ok, detail, loading=not model_loaded)
        except HTTPError as exc:
            return ServiceHealth(False, f"HTTP {exc.code}", loading=exc.code == 503)
        except (URLError, OSError) as exc:
            return ServiceHealth(False, str(exc))


def create_asr_client(config: dict[str, Any]) -> WhisperXASRClient | WhisperASRClient:
    provider = str(config.get("provider", "whisperx")).strip().lower()
    if provider == "whisperx":
        return WhisperXASRClient(config)
    return WhisperASRClient(config)


_VLM_DEFAULT_PROMPT = (
    "Отвечай только по-русски. Не используй китайские иероглифы. "
    "Кратко опиши сцену в одном предложении: люди, движения, заметные объекты."
)

# CJK Unified Ideographs (U+4E00..U+9FFF) — VILA 1.5-3b sometimes outputs Chinese
# despite Russian prompt; we count these to detect and reject such replies.
_CJK_RE = re.compile(r"[一-鿿]")
_CJK_REJECT_THRESHOLD = 3  # 3+ Chinese ideographs → reject and retry

_VLM_RUSSIAN_RETRY_PROMPT = (
    "ВНИМАНИЕ: отвечай только по-русски кириллицей. Не используй китайские иероглифы. "
    "Опиши сцену одним коротким предложением на русском языке: "
    "люди, движения, заметные объекты."
)


class VLMClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "http://127.0.0.1:8084")).rstrip("/")
        self.timeout = float(config.get("timeout_sec", 15))
        self.model = str(config.get("model", "Efficient-Large-Model/VILA1.5-3b"))
        self.max_new_tokens = int(config.get("max_new_tokens", 48))
        self.prompt = str(config.get("prompt", _VLM_DEFAULT_PROMPT))
        self._session: Any = None

    def _get_session(self) -> Any:
        if self._session is None or self._session.is_closed:
            import httpx
            self._session = httpx.Client(base_url=self.base_url, timeout=self.timeout, trust_env=False)
        return self._session

    async def health(self) -> ServiceHealth:
        return await asyncio.to_thread(self._health_sync)

    def _health_sync(self) -> ServiceHealth:
        paths = ("/health", "/v1/models", "/")
        last_error = "vlm health probe failed"
        last_loading = False
        for path in paths:
            try:
                req = Request(self.base_url + path, method="GET")
                with urlopen(req, timeout=2) as resp:  # short timeout for health only
                    return ServiceHealth(resp.status < 500, f"HTTP {resp.status} {path}")
            except HTTPError as exc:
                last_error = f"HTTP {exc.code} {path}"
                last_loading = exc.code == 503
            except (URLError, OSError) as exc:
                last_error = str(exc)
                last_loading = False
        return ServiceHealth(False, last_error, loading=last_loading)

    async def describe_jpeg(self, jpeg_bytes: bytes) -> str:
        return await asyncio.to_thread(self._describe_jpeg_sync, jpeg_bytes)

    def _describe_jpeg_sync(self, jpeg_bytes: bytes) -> str:
        if not jpeg_bytes:
            raise RuntimeError("empty scene snapshot")
        image_b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        # Try with default prompt first; if reply has too many CJK ideographs,
        # retry with a stronger Russian-only directive.
        for attempt_prompt in (self.prompt, _VLM_RUSSIAN_RETRY_PROMPT):
            text = self._call_vlm(image_b64, attempt_prompt)
            if text and not self._is_chinese_dominant(text):
                return text
            if text and self._is_chinese_dominant(text) and attempt_prompt is self.prompt:
                # First attempt produced Chinese — fall through to retry
                continue
            if text:
                # Retry also produced Chinese — reject (caller will keep stale scene)
                raise RuntimeError(
                    f"vlm returned non-russian output (cjk count >= {_CJK_REJECT_THRESHOLD})"
                )
        raise RuntimeError("vlm returned no scene description")

    def _call_vlm(self, image_b64: str, prompt_text: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    ],
                }
            ],
            "max_tokens": self.max_new_tokens,
            "stream": False,
        }
        errors: list[str] = []
        for path in ("/v1/chat/completions", "/chat/completions"):
            try:
                raw = self._post(path, payload)
                text = self._extract_chat_text(raw)
                if text:
                    return text
            except (HTTPError, URLError, OSError, json.JSONDecodeError, RuntimeError) as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
        return ""

    @staticmethod
    def _is_chinese_dominant(text: str) -> bool:
        return len(_CJK_RE.findall(text)) >= _CJK_REJECT_THRESHOLD

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._get_session().post(path, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            return resp.json()
        except Exception:
            body = json.dumps(payload).encode("utf-8")
            req = Request(self.base_url + path, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urlopen(req, timeout=self.timeout) as resp_u:
                return json.loads(resp_u.read().decode("utf-8"))

    @staticmethod
    def _extract_chat_text(raw: dict[str, Any]) -> str:
        choices = raw.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
                return " ".join(part for part in parts if part).strip()
        for key in ("text", "response", "caption", "description"):
            if raw.get(key):
                return str(raw[key]).strip()
        return ""


class SceneCache:
    def __init__(self) -> None:
        self.text = ""
        self.meta: dict[str, Any] = {}
        self.updated_at = ""
        self.source = "manual"
        self.stale = True
        self._updated_ts: float = 0.0

    def update(self, text: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        self.text = text.strip()
        self.meta = meta or {}
        self.updated_at = str(self.meta.get("updated_at") or datetime.now(timezone.utc).isoformat())
        self.source = str(self.meta.get("source", "manual"))
        self.stale = bool(self.meta.get("stale", False))
        self._updated_ts = time.monotonic()
        return self.as_dict()

    def mark_stale(self, error: str | None = None) -> dict[str, Any]:
        self.stale = True
        if error:
            self.meta = {**self.meta, "last_error": error}
        return self.as_dict()

    def is_time_stale(self, stale_after_sec: float) -> bool:
        if self._updated_ts == 0.0:
            return True
        return (time.monotonic() - self._updated_ts) > stale_after_sec

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "summary": self.text,
            "updated_at": self.updated_at,
            "source": self.source,
            "stale": self.stale,
            "meta": self.meta,
        }


_WHITESPACE_RE = re.compile(r"\s+")
# Split on sentence-ending punctuation followed by whitespace.
# Includes em-dash (—) which is common in Russian text as a clause separator.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？—])\s+")


def split_sentences(text: str) -> list[str]:
    text = _WHITESPACE_RE.sub(" ", text.strip())
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text)
    return [part.strip() for part in parts if part.strip()]

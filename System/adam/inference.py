from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


class TTSClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "http://127.0.0.1:8082")).rstrip("/")
        self.timeout = float(config.get("timeout_sec", 20))
        self.speaker = str(config.get("speaker", "eugene"))
        self.output_device = str(config.get("output_device", "")).strip()
        self._current_play_proc: Any = None  # active aplay Popen handle for barge-in interrupt
        self._session: Any = None

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
        """Play WAV bytes locally. Blocks until playback completes.

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

    def interrupt_playback(self) -> None:
        """Kill the active aplay process (barge-in). Safe to call from any thread."""
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
        self.base_url = str(config.get("base_url", "http://127.0.0.1:8083")).rstrip("/")
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
    "Briefly describe the scene in one sentence: people present, movement, notable objects."
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
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt},
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
        raise RuntimeError("; ".join(errors) or "vlm returned no scene description")

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

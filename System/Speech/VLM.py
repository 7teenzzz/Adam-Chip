#!/usr/bin/env python3
"""
Adam Chip VLM HTTP Microservice — OpenAI-compatible vision endpoint.

Designed to run inside dustynv/nano_llm Docker container.
Uses stdlib http.server only — no FastAPI/Flask/pydantic dependency.

  GET  /health               → {"ok": bool, "model_loaded": bool, "loading": bool}
  GET  /v1/models            → {"data": [{"id": model_name}]}
  POST /v1/chat/completions  → OpenAI choices format (vision via image_url)

ENV vars (all optional):
  ADAM_VLM_HOST        bind address   (default: 0.0.0.0)
  ADAM_VLM_PORT        HTTP port      (default: 8050)
  ADAM_VLM_MODEL       model name     (default: Efficient-Large-Model/VILA1.5-3b)
  ADAM_VLM_MAX_TOKENS  max_new_tokens (default: 48)
  HF_HOME              HF cache dir   (default: /data/models/huggingface)
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VLM] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("vlm")

_MODEL_NAME = os.environ.get("ADAM_VLM_MODEL", "Efficient-Large-Model/VILA1.5-3b")
_MAX_NEW_TOKENS = int(os.environ.get("ADAM_VLM_MAX_TOKENS", "48"))

_MODEL: Any = None
_MODEL_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()  # MLC GPU inference is single-threaded
_MODEL_ERROR: str = ""
_MODEL_LOADING: bool = False


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class VLMHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._handle_health()
        elif path == "/v1/models":
            self._handle_models()
        elif path == "/":
            self._send_json(200, {"service": "adam-vlm", "model": _MODEL_NAME})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/v1/chat/completions", "/chat/completions"):
            self._handle_chat()
        else:
            self._send_json(404, {"error": "not found"})

    # ------------------------------------------------------------------
    def _handle_health(self) -> None:
        ok = _MODEL is not None and not _MODEL_ERROR
        self._send_json(200 if ok else 503, {
            "ok": ok,
            "provider": "nano_llm",
            "model_loaded": _MODEL is not None,
            "model": _MODEL_NAME,
            "loading": _MODEL_LOADING,
            "error": _MODEL_ERROR or None,
        })

    def _handle_models(self) -> None:
        if _MODEL is None:
            self._send_json(503, {"error": "model not loaded yet", "loading": _MODEL_LOADING})
            return
        self._send_json(200, {
            "object": "list",
            "data": [{"id": _MODEL_NAME, "object": "model", "owned_by": "nano_llm"}],
        })

    def _handle_chat(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "invalid JSON body"})
            return

        if _MODEL is None:
            self._send_json(503, {"error": "model not loaded yet", "loading": _MODEL_LOADING})
            return

        messages = payload.get("messages", [])
        max_tokens = min(int(payload.get("max_tokens", _MAX_NEW_TOKENS)), _MAX_NEW_TOKENS)

        prompt_text, image_bytes = _parse_vision_message(messages)
        if not prompt_text:
            self._send_json(400, {"error": "no text prompt found in messages"})
            return

        try:
            result = _infer(prompt_text, image_bytes, max_tokens)
        except RuntimeError as exc:
            log.error("inference error: %s", exc)
            self._send_json(503, {"error": str(exc)})
            return

        self._send_json(200, {
            "id": f"vlm-{int(time.time())}",
            "object": "chat.completion",
            "model": _MODEL_NAME,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": -1, "completion_tokens": -1, "total_tokens": -1},
        })

    # ------------------------------------------------------------------
    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default logs
        if self.path == "/health":
            return
        log.info("HTTP %s %s", self.command, self.path)


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def _parse_vision_message(messages: list[dict]) -> tuple[str, bytes | None]:
    """Extract (prompt_text, jpeg_bytes) from OpenAI vision message list."""
    prompt_text = ""
    image_bytes: bytes | None = None
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            prompt_text = content
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "text":
                    prompt_text = part.get("text", "")
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:image/") and "base64," in url:
                        b64 = url.split("base64,", 1)[1]
                        image_bytes = base64.b64decode(b64)
    return prompt_text, image_bytes


def _infer(prompt_text: str, image_bytes: bytes | None, max_tokens: int) -> str:
    """Run VILA inference. Serialized via _INFER_LOCK (MLC is single-threaded)."""
    from nano_llm import ChatHistory

    with _INFER_LOCK:
        chat = ChatHistory(_MODEL)

        if image_bytes is not None:
            from PIL import Image
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # VILA requires interleaved ordering: image entry first, then text entry.
            chat.append(role="user", image=pil_image)
            chat.append(role="user", text=prompt_text)
        else:
            chat.append(role="user", text=prompt_text)

        embedding, _ = chat.embed_chat()

        output = _MODEL.generate(
            inputs=embedding,
            kv_cache=chat.kv_cache,
            stop_tokens=chat.template.stop,
            max_new_tokens=max_tokens,
            streaming=False,
            do_sample=False,
        )

    return _extract_text(output)


_STOP_TOKENS = ("</s>", "<|end|>", "<|im_end|>", "<|eot_id|>", "<end_of_turn>")


def _extract_text(output: Any) -> str:
    """Robustly extract string from nano_llm generate() result."""
    if output is None:
        return ""
    if hasattr(output, "text"):
        text = str(output.text)
    elif isinstance(output, str):
        text = output
    else:
        try:
            tokens = list(output)
            text = output.text if hasattr(output, "text") else "".join(str(t) for t in tokens)
        except Exception:
            text = str(output)
    text = text.strip()
    for stop in _STOP_TOKENS:
        if text.endswith(stop):
            text = text[: -len(stop)].strip()
    return text


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _eager_load() -> None:
    """Load model in a background thread so /health returns 503 during startup."""
    global _MODEL, _MODEL_ERROR, _MODEL_LOADING
    _MODEL_LOADING = True
    try:
        log.info("Loading VLM model: %s", _MODEL_NAME)
        t0 = time.perf_counter()
        from nano_llm import NanoLLM
        model = NanoLLM.from_pretrained(
            _MODEL_NAME,
            api="mlc",
            quantization="q4f16_ft",
        )
        with _MODEL_LOCK:
            _MODEL = model
        elapsed = round(time.perf_counter() - t0, 1)
        log.info("VLM model loaded in %.1fs", elapsed)
    except Exception as exc:
        with _MODEL_LOCK:
            _MODEL_ERROR = str(exc)
        log.error("VLM model load failed: %s", exc)
    finally:
        _MODEL_LOADING = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    host = os.environ.get("ADAM_VLM_HOST", "0.0.0.0")
    port = int(os.environ.get("ADAM_VLM_PORT", "8050"))

    threading.Thread(target=_eager_load, daemon=True, name="vlm_loader").start()

    log.info("Starting VLM HTTP service on %s:%d — model loading in background", host, port)
    server = ThreadingHTTPServer((host, port), VLMHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()

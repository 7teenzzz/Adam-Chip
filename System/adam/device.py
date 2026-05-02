from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


@dataclass
class DeviceResult:
    ok: bool
    status: int
    data: dict[str, Any]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "data": self.data,
            "error": self.error,
        }


class MCUClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "http://192.168.0.171")).rstrip("/")
        self.speaker_url = str(config.get("speaker_url", "http://192.168.0.171:83/speaker")).strip()
        self.timeout = float(config.get("timeout_sec", 3))
        self.idle_scene = str(config.get("idle_scene", "boot_idle"))
        self.allowed_scenes = set(config.get("allowed_scenes", ["boot_idle"]))
        channels = config.get("channels", {})
        self.channel_min = int(channels.get("min", 0))
        self.channel_max = int(channels.get("max", 15))
        self.value_min = int(channels.get("value_min", 0))
        self.value_max = int(channels.get("value_max", 4095))

    async def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> DeviceResult:
        return await asyncio.to_thread(self._request, method, path, payload)

    async def health(self) -> DeviceResult:
        return await asyncio.to_thread(self._request, "GET", "/api/status")

    async def sensor_snapshot(self) -> DeviceResult:
        return await asyncio.to_thread(self._request, "GET", "/api/sensors")

    async def idle(self) -> DeviceResult:
        return await self.set_scene(self.idle_scene)

    async def set_scene(self, scene: str) -> DeviceResult:
        if scene not in self.allowed_scenes:
            return DeviceResult(False, 400, {}, f"scene_not_allowed:{scene}")
        return await asyncio.to_thread(self._request, "POST", "/api/pca9685/scene", {"scene": scene})

    async def set_channel(self, channel: int, value: int) -> DeviceResult:
        channel = max(self.channel_min, min(self.channel_max, int(channel)))
        value = max(self.value_min, min(self.value_max, int(value)))
        payload = {"channel": channel, "mode": "pwm", "value": value}
        return await asyncio.to_thread(self._request, "POST", "/api/pca9685/channel", payload)

    async def set_channels(self, updates: list[dict[str, Any]]) -> DeviceResult:
        normalized: list[dict[str, Any]] = []
        for item in updates:
            channel = max(self.channel_min, min(self.channel_max, int(item.get("channel", 0))))
            mode = str(item.get("mode", "pwm")).strip() or "pwm"
            value = max(self.value_min, min(self.value_max, int(item.get("value", 0))))
            normalized.append({"channel": channel, "mode": mode, "value": value})
        if not normalized:
            return DeviceResult(False, 400, {}, "updates_required")
        return await asyncio.to_thread(self._request, "POST", "/api/pca9685/channels", {"updates": normalized})

    async def play_system_sound(self, name: str) -> DeviceResult:
        name = str(name).strip()
        if name not in {"boot", "tone", "success"}:
            return DeviceResult(False, 400, {}, f"invalid_sound:{name}")
        return await asyncio.to_thread(self._request, "POST", f"/api/sound/play?name={name}")

    async def post_speaker_bytes(self, data: bytes, content_type: str = "audio/wav") -> DeviceResult:
        return await asyncio.to_thread(self._post_raw, self.speaker_url, data, content_type)

    def camera_stream_url(self) -> str:
        return self._url_for_port(81, "/stream")

    def mic_stream_url(self) -> str:
        return self._url_for_port(82, "/audio")

    def speaker_endpoint_url(self) -> str:
        return self.speaker_url

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> DeviceResult:
        target = urljoin(self.base_url + "/", path.lstrip("/"))
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(target, data=body, method=method)
        req.add_header("Accept", "application/json")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return DeviceResult(True, resp.status, self._decode_json(raw))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return DeviceResult(False, exc.code, self._decode_json(raw), raw)
        except (URLError, TimeoutError, OSError) as exc:
            return DeviceResult(False, 0, {}, str(exc))

    def _post_raw(self, target: str, data: bytes, content_type: str) -> DeviceResult:
        req = Request(target, data=data, method="POST")
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", content_type)
        try:
            with urlopen(req, timeout=max(self.timeout, 20.0)) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return DeviceResult(True, resp.status, self._decode_json(raw))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return DeviceResult(False, exc.code, self._decode_json(raw), raw)
        except (URLError, TimeoutError, OSError) as exc:
            return DeviceResult(False, 0, {}, str(exc))

    def _url_for_port(self, port: int, path: str) -> str:
        parsed = urlsplit(self.base_url)
        scheme = parsed.scheme or "http"
        hostname = parsed.hostname or parsed.netloc.split(":")[0]
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        return urlunsplit((scheme, f"{hostname}:{port}", path, "", ""))

    @staticmethod
    def _decode_json(raw: str) -> dict[str, Any]:
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {"value": value}
        except json.JSONDecodeError:
            return {"raw": raw}

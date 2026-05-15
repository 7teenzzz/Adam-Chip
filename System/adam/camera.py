from __future__ import annotations

import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from typing import Any

_MJPEG_JPEG_SOI = b"\xff\xd8"
_MJPEG_JPEG_EOI = b"\xff\xd9"
_MJPEG_BUF_LIMIT = 512 * 1024  # 512 KB safety cap per frame scan


class CameraReader:
    """Persistent background camera capture with thread-safe frame buffer.

    When primary == "esp_mjpeg": fetches frames from ESP32 MJPEG stream.
    On N consecutive failures switches to Jetson fallback (cv2 or gst subprocess).
    Probes ESP32 every esp_retry_interval_sec and restores primary when available.

    Otherwise: tries cv2+GStreamer backend first (native on Jetson), then gst subprocess.
    """

    def __init__(self, video_config: dict[str, Any]) -> None:
        self.primary = str(video_config.get("primary", "jetson_gstreamer"))
        self.device = str(video_config.get("video_device", "/dev/video0"))
        self.width = int(video_config.get("camera_width", 640))
        self.height = int(video_config.get("camera_height", 480))
        self.quality = int(video_config.get("camera_quality", 75))
        self.capture_interval = float(video_config.get("camera_capture_interval_sec", 0.5))
        self.esp_mjpeg_url = str(video_config.get("esp_mjpeg_url", ""))
        self.esp_fail_threshold = int(video_config.get("esp_fail_threshold", 3))
        self.esp_retry_interval_sec = float(video_config.get("esp_retry_interval_sec", 30.0))

        self._latest: bytes = b""
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._frame_count = 0
        self._last_error = ""

        self._active_source: str = "esp" if self.primary == "esp_mjpeg" else "jetson"
        self._esp_fail_count: int = 0
        self._esp_last_retry: float = 0.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="adam_camera")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def get_latest(self) -> bytes:
        with self._lock:
            return self._latest

    @property
    def has_frame(self) -> bool:
        with self._lock:
            return bool(self._latest)

    @property
    def active_source(self) -> str:
        return self._active_source

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "has_frame": self.has_frame,
            "frame_count": self._frame_count,
            "last_error": self._last_error,
            "device": self.device,
            "active_source": self._active_source,
        }

    def apply_config(self, video_cfg: dict[str, Any]) -> bool:
        """Apply video config changes at runtime. Returns True if restart is needed."""
        new_primary = str(video_cfg.get("primary", self.primary))
        new_url = str(video_cfg.get("esp_mjpeg_url", self.esp_mjpeg_url))
        self.esp_mjpeg_url = new_url
        self.capture_interval = float(video_cfg.get("camera_capture_interval_sec", self.capture_interval))
        if new_primary != self.primary:
            self.primary = new_primary
            self._active_source = "esp" if new_primary == "esp_mjpeg" else "jetson"
            self._esp_fail_count = 0
            self._esp_last_retry = 0.0
            return True
        return False

    def restart(self) -> None:
        """Stop and restart the camera capture thread."""
        self.stop()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="adam_camera")
        self._thread.start()

    # ------------------------------------------------------------------
    # Internal loop dispatch
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        if self.primary == "esp_mjpeg" and self.esp_mjpeg_url:
            self._esp_mjpeg_loop()
            return
        if self._cv2_loop():
            return
        self._gst_loop()

    # ------------------------------------------------------------------
    # ESP32 MJPEG primary loop with Jetson fallback
    # ------------------------------------------------------------------

    def _esp_mjpeg_loop(self) -> None:
        while self._running:
            t = time.perf_counter()
            try:
                if self._active_source == "jetson_fallback":
                    self._maybe_restore_esp()
                if self._active_source == "esp":
                    jpeg = self._fetch_esp_jpeg()
                else:
                    jpeg = self._jetson_snap_once()

                if jpeg:
                    with self._lock:
                        self._latest = jpeg
                        self._frame_count += 1
                    self._last_error = ""
                    if self._active_source == "esp":
                        self._esp_fail_count = 0
                else:
                    raise RuntimeError("empty frame")

            except Exception as exc:
                self._last_error = str(exc)
                if self._active_source == "esp":
                    self._esp_fail_count += 1
                    if self._esp_fail_count >= self.esp_fail_threshold:
                        self._active_source = "jetson_fallback"
                        self._esp_last_retry = time.perf_counter()

            elapsed = time.perf_counter() - t
            time.sleep(max(0.0, self.capture_interval - elapsed))

    def _maybe_restore_esp(self) -> None:
        if time.perf_counter() - self._esp_last_retry < self.esp_retry_interval_sec:
            return
        self._esp_last_retry = time.perf_counter()
        if self._esp_probe():
            self._active_source = "esp"
            self._esp_fail_count = 0

    def _esp_probe(self) -> bool:
        try:
            with urllib.request.urlopen(self.esp_mjpeg_url, timeout=2):
                return True
        except Exception:
            return False

    def _fetch_esp_jpeg(self) -> bytes:
        """Open ESP32 MJPEG stream, extract one JPEG frame by SOI/EOI markers, close."""
        req = urllib.request.Request(self.esp_mjpeg_url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            buf = b""
            soi = -1
            while len(buf) < _MJPEG_BUF_LIMIT:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buf += chunk
                if soi == -1:
                    soi = buf.find(_MJPEG_JPEG_SOI)
                if soi != -1:
                    eoi = buf.find(_MJPEG_JPEG_EOI, soi)
                    if eoi != -1:
                        return buf[soi : eoi + 2]
        raise RuntimeError("MJPEG: JPEG frame not found in stream")

    def _jetson_snap_once(self) -> bytes:
        """One-shot Jetson camera frame for fallback mode."""
        try:
            import cv2  # type: ignore[import-not-found]
            cap = cv2.VideoCapture(self.device)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                    return buf.tobytes()
        except ImportError:
            pass
        return self._gst_snap()

    # ------------------------------------------------------------------
    # Jetson primary loops (unchanged)
    # ------------------------------------------------------------------

    def _cv2_loop(self) -> bool:
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError:
            return False

        gst_pipe = (
            f"v4l2src device={self.device} ! image/jpeg ! jpegdec ! videoscale ! "
            f"video/x-raw,width={self.width},height={self.height} ! videoconvert ! appsink drop=true max-buffers=1"
        )
        cap = cv2.VideoCapture(gst_pipe, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.device)
        if not cap.isOpened():
            return False

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.quality]
        try:
            while self._running:
                ret, frame = cap.read()
                if ret:
                    _, buf = cv2.imencode(".jpg", frame, encode_params)
                    data = buf.tobytes()
                    with self._lock:
                        self._latest = data
                        self._frame_count += 1
                    self._last_error = ""
                else:
                    self._last_error = "cv2.read() returned False"
                time.sleep(self.capture_interval)
        finally:
            cap.release()
        return True

    def _gst_loop(self) -> None:
        while self._running:
            t = time.perf_counter()
            try:
                frame = self._gst_snap()
                if frame:
                    with self._lock:
                        self._latest = frame
                        self._frame_count += 1
                    self._last_error = ""
                else:
                    self._last_error = "empty gst snapshot"
            except Exception as exc:
                self._last_error = str(exc)
            elapsed = time.perf_counter() - t
            time.sleep(max(0.0, self.capture_interval - elapsed))

    def _gst_snap(self) -> bytes:
        gst = shutil.which("gst-launch-1.0")
        if not gst:
            raise RuntimeError("gst-launch-1.0 not found")
        proc = subprocess.run(
            [
                gst, "-q",
                "v4l2src", f"device={self.device}", "num-buffers=1",
                "!", "image/jpeg",
                "!", "jpegdec",
                "!", "videoscale",
                "!", f"video/x-raw,width={self.width},height={self.height}",
                "!", "jpegenc", f"quality={self.quality}",
                "!", "fdsink", "fd=1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[-200:])
        return proc.stdout


class SceneDescriptionBuffer:
    """Thread-safe ring buffer of recent VLM scene descriptions."""

    def __init__(self, maxlen: int = 8) -> None:
        self._buf: deque[str] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def push(self, text: str) -> None:
        stripped = text.strip()
        if stripped:
            with self._lock:
                self._buf.append(stripped)

    def latest(self) -> str:
        with self._lock:
            return self._buf[-1] if self._buf else ""

    def recent(self, n: int = 3) -> list[str]:
        with self._lock:
            items = list(self._buf)
        return items[-n:] if items else []

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)

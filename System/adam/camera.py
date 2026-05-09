from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Any


class CameraReader:
    """Persistent background camera capture with thread-safe frame buffer.

    Tries cv2+GStreamer backend first (native on Jetson); falls back to
    periodic gst-launch-1.0 subprocess if cv2 is unavailable.
    """

    def __init__(self, video_config: dict[str, Any]) -> None:
        self.device = str(video_config.get("video_device", "/dev/video0"))
        self.width = int(video_config.get("camera_width", 640))
        self.height = int(video_config.get("camera_height", 480))
        self.quality = int(video_config.get("camera_quality", 75))
        self.capture_interval = float(video_config.get("camera_capture_interval_sec", 0.5))
        self._latest: bytes = b""
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._frame_count = 0
        self._last_error = ""

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

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "has_frame": self.has_frame,
            "frame_count": self._frame_count,
            "last_error": self._last_error,
            "device": self.device,
        }

    # ------------------------------------------------------------------
    # Internal loop — tries cv2, falls back to gst subprocess
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        if self._cv2_loop():
            return
        self._gst_loop()

    def _cv2_loop(self) -> bool:
        try:
            import cv2  # type: ignore[import-not-found]
        except ImportError:
            return False

        # Try GStreamer pipeline first (hardware-accelerated on Jetson)
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

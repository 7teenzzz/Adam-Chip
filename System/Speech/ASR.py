#!/usr/bin/env python3
from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any


@dataclass
class RivaASRConfig:
    host: str = "127.0.0.1"
    port: int = 50051
    language_code: str = "ru-RU"
    endpointing_ms: int = 450


class RivaASRService:
    """Health adapter for the external NVIDIA Riva streaming ASR service.

    Streaming recognition should be implemented with the Riva Python gRPC client
    in the deployment environment where the Riva client wheels/protos are
    installed. The orchestrator treats ASR as a service boundary so that this
    module can stay lightweight in the repo.
    """

    def __init__(self, config: RivaASRConfig) -> None:
        self.config = config

    def health(self, timeout: float = 1.0) -> dict[str, Any]:
        try:
            with socket.create_connection((self.config.host, self.config.port), timeout=timeout):
                return {"ok": True, "endpoint": f"{self.config.host}:{self.config.port}"}
        except OSError as exc:
            return {"ok": False, "endpoint": f"{self.config.host}:{self.config.port}", "error": str(exc)}

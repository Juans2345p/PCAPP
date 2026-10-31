# -*- coding: utf-8 -*-
"""Servidor local para la interfaz web del control gestual."""

from __future__ import annotations

import json
import logging
import mimetypes
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import cv2

LOG = logging.getLogger("gesture-cart.web")
WEB_DIR = Path(__file__).with_name("web")
_CONFIG_KEYS = {"deadzone", "smoothing", "step", "lost_grace", "speed_multiplier"}
_ACTIONS = {"toggle_running", "toggle_hands", "exit"}


class _DashboardHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class WebDashboard:
    """Sirve HTML, estado y video MJPEG y entrega acciones al bucle Python."""

    def __init__(self, port: int = 8765) -> None:
        self._port = port
        self._condition = threading.Condition()
        self._jpeg: bytes | None = None
        self._sequence = 0
        self._state: dict[str, Any] = {}
        self._actions: queue.Queue[dict[str, Any]] = queue.Queue()
        self._closed = False
        dashboard = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt: str, *args: Any) -> None:
                LOG.debug("web %s - %s", self.address_string(), fmt % args)

            def do_GET(self) -> None:
                path = urlparse(self.path).path
                if path == "/":
                    self._static("index.html")
                elif path in ("/app.js", "/style.css"):
                    self._static(path.lstrip("/"))
                elif path == "/api/state":
                    self._json(200, dashboard.state())
                elif path == "/stream.mjpg":
                    self._stream()
                else:
                    self._json(404, {"error": "No encontrado"})

            def do_POST(self) -> None:
                if urlparse(self.path).path not in ("/api/action", "/api/config"):
                    self._json(404, {"error": "No encontrado"})
                    return
                try:
                    length = min(int(self.headers.get("Content-Length", "0")), 4096)
                    payload = json.loads(self.rfile.read(length) or b"{}")
                except (ValueError, json.JSONDecodeError):
                    self._json(400, {"error": "Solicitud JSON inválida"})
                    return
                if not isinstance(payload, dict):
                    self._json(400, {"error": "Se esperaba un objeto JSON"})
                    return
                if urlparse(self.path).path == "/api/action":
                    action = payload.get("action")
                    if action not in _ACTIONS:
                        self._json(400, {"error": "Acción desconocida"})
                        return
                    dashboard.submit({"type": "action", "action": action})
                else:
                    key, value = payload.get("key"), payload.get("value")
                    if key not in _CONFIG_KEYS or isinstance(value, bool):
                        self._json(400, {"error": "Parámetro desconocido"})
                        return
                    try:
                        number = float(value)
                    except (TypeError, ValueError):
                        self._json(400, {"error": "El valor debe ser numérico"})
                        return
                    dashboard.submit({"type": "config", "key": key, "value": number})
                self._json(202, {"accepted": True})

            def _json(self, status: int, value: dict[str, Any]) -> None:
                data = json.dumps(value, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def _static(self, name: str) -> None:
                path = WEB_DIR / name
                try:
                    data = path.read_bytes()
                except OSError:
                    self._json(404, {"error": "Recurso no encontrado"})
                    return
                content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
                if name.endswith(".js"):
                    content_type = "text/javascript"
                self.send_response(200)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data)

            def _stream(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Connection", "close")
                self.end_headers()
                last_sequence = -1
                try:
                    while not dashboard._closed:
                        with dashboard._condition:
                            dashboard._condition.wait_for(
                                lambda: dashboard._closed or dashboard._sequence != last_sequence,
                                timeout=1.0,
                            )
                            jpeg = dashboard._jpeg
                            sequence = dashboard._sequence
                        if jpeg is None or sequence == last_sequence:
                            continue
                        last_sequence = sequence
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n"
                            + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
                            + jpeg
                            + b"\r\n"
                        )
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    return

        self._server = _DashboardHTTPServer(("127.0.0.1", port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="web-dashboard",
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    def start(self) -> None:
        self._thread.start()
        LOG.info("Interfaz web disponible en %s", self.url)

    def publish(self, frame, poses, sender, controller, settings, fps: float) -> None:
        ok, encoded = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92]
        )
        if not ok:
            return
        command = controller.last_command
        hands: dict[str, dict[str, float]] = {}
        for side, pose in poses.items():
            if pose.landmarks:
                wrist = pose.landmarks[0]
                hands[side] = {"x": float(wrist.x), "y": float(wrist.y)}
        state = {
            "running": controller.enabled,
            "connected": bool(getattr(sender, "connected", False)),
            "dry_run": bool(getattr(sender, "is_dry_run", False)),
            "address": settings.address,
            "device_name": settings.name or "BBC micro:bit",
            "fps": round(float(fps), 1),
            "hands_count": len(poses),
            "hands": hands,
            "left": command.left,
            "right": command.right,
            "max_speed": settings.max_speed,
            "camera": settings.camera,
            "frame_width": settings.width,
            "frame_height": settings.height,
            "deadzone": settings.deadzone,
            "smoothing": settings.smoothing,
            "step": settings.step,
            "lost_grace": settings.lost_grace,
            "speed_multiplier": settings.speed_multiplier,
            "single_hand": settings.single_hand,
            "last_payload": controller.last_payload,
            "sent": int(getattr(sender, "sent", 0)),
            "dropped": int(getattr(sender, "dropped", 0)),
        }
        with self._condition:
            self._jpeg = encoded.tobytes()
            self._sequence += 1
            self._state = state
            self._condition.notify_all()

    def state(self) -> dict[str, Any]:
        with self._condition:
            return dict(self._state)

    def submit(self, action: dict[str, Any]) -> None:
        self._actions.put(action)

    def take_actions(self) -> list[dict[str, Any]]:
        actions = []
        while True:
            try:
                actions.append(self._actions.get_nowait())
            except queue.Empty:
                return actions

    def close(self) -> None:
        self._closed = True
        with self._condition:
            self._condition.notify_all()
        self._server.shutdown()
        self._server.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

# -*- coding: utf-8 -*-
"""Captura de webcam en un hilo aparte."""

from __future__ import annotations

import contextlib
import threading
import time

import cv2
import numpy as np


class FrameGrabber(threading.Thread):
    """Lee la webcam en segundo plano y expone siempre el último frame."""

    def __init__(self, index: int, width: int, height: int) -> None:
        super().__init__(name="camera", daemon=True)
        self._cap = self._open(index, width, height)
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._seq = 0
        self._stop = threading.Event()
        self.fps = 0.0

    @staticmethod
    def _open(index: int, width: int, height: int) -> cv2.VideoCapture:
        api = getattr(cv2, "CAP_V4L2", 0)
        capture = cv2.VideoCapture(index, api)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(index)
        if not capture.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara {index}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, 30)
        with contextlib.suppress(Exception):
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # baja latencia en V4L2
        return capture

    def run(self) -> None:
        previous = time.monotonic()
        frames = 0
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            with self._lock:
                self._frame = frame
                self._seq += 1
            frames += 1
            now = time.monotonic()
            if now - previous >= 1.0:
                self.fps = frames / (now - previous)
                frames, previous = 0, now

    def latest(self) -> tuple[np.ndarray | None, int]:
        with self._lock:
            return self._frame, self._seq

    def stop(self) -> None:
        self._stop.set()

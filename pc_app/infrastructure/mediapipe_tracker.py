# -*- coding: utf-8 -*-
"""Reconocedor de manos basado en MediaPipe Tasks (HandLandmarker)."""

from __future__ import annotations

import contextlib
import math
import time
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

from pc_app.config import Settings
from pc_app.domain.entities.hand_pose import HandPose
from pc_app.domain.interfaces.gesture_recognizer import IGestureRecognizer

INDEX_CHAIN = (5, 6, 7, 8)      # MCP, PIP, DIP, TIP del índice
MIDDLE_CHAIN = (9, 10, 11, 12)  # MCP, PIP, DIP, TIP del corazón


class MediaPipeHandTracker(IGestureRecognizer):
    """Envoltorio de `HandLandmarker` en modo VIDEO."""

    def __init__(self, settings: Settings) -> None:
        options = vision.HandLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(settings.model)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=settings.num_hands,
            min_hand_detection_confidence=settings.detect_conf,
            min_hand_presence_confidence=settings.presence_conf,
            min_tracking_confidence=settings.track_conf,
        )
        self._settings = settings
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._t0 = time.monotonic()
        self._last_ts = -1
        # Filtro EMA por mano y dedo: {(side, "index"|"middle"): valor}
        self._ema: dict[tuple[str, str], float | None] = {}

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._landmarker.close()

    # -- internos ------------------------------------------------------------
    def _timestamp_ms(self) -> int:
        """MediaPipe VIDEO exige timestamps estrictamente crecientes."""
        timestamp = int((time.monotonic() - self._t0) * 1000)
        if timestamp <= self._last_ts:
            timestamp = self._last_ts + 1
        self._last_ts = timestamp
        return timestamp

    @staticmethod
    def _straightness(landmarks: list[Any], chain: tuple[int, ...],
                      width: int, height: int) -> float:
        """Cuerda / camino de la cadena de falanges -> 0 (curvado) .. 1 (recto)."""
        points = [(landmarks[i].x * width, landmarks[i].y * height) for i in chain]
        path = sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))
        if path < 1e-6:
            return 0.0
        return math.dist(points[0], points[-1]) / path

    def _to_extension(self, raw: float, side: str, key: str) -> float:
        """Normaliza, aplica zona muerta y suaviza con EMA (estado por mano)."""
        cfg = self._settings
        if cfg.curl_hi <= cfg.curl_lo:
            value = 0.0
        else:
            value = (raw - cfg.curl_lo) / (cfg.curl_hi - cfg.curl_lo)
            value = max(0.0, min(1.0, value))
        if value < cfg.deadzone:
            value = 0.0
        else:  # reescala para que siga llegando a 1.0 tras la zona muerta
            value = (value - cfg.deadzone) / (1.0 - cfg.deadzone)

        previous = self._ema.get((side, key))
        smoothed = value if previous is None else previous + cfg.smoothing * (value - previous)
        self._ema[(side, key)] = smoothed
        return smoothed

    @staticmethod
    def _handedness(result: Any, index: int) -> str:
        """Etiqueta cruda de MediaPipe ('Left' / 'Right') o '' si no hay."""
        try:
            entry = result.handedness[index]
        except (AttributeError, IndexError, TypeError):
            return ""
        category = entry[0] if isinstance(entry, (list, tuple)) and entry else entry
        for attr in ("category_name", "display_name", "label"):
            name = getattr(category, attr, None)
            if name:
                return str(name)
        return ""

    def _side(self, result: Any, index: int, landmarks: list[Any]) -> str:
        """Traduce la etiqueta de MediaPipe a 'L'/'R' teniendo en cuenta el espejo."""
        label = self._handedness(result, index).lower()
        cfg = self._settings
        if "left" in label:
            side = "L"
        elif "right" in label:
            side = "R"
        else:
            # Sin etiqueta: en vista espejo la mano izquierda aparece a la izquierda.
            side = "L" if (landmarks[0].x < 0.5) == cfg.mirror else "R"

        # MediaPipe asume que la imagen YA viene espejada (selfie). Si no lo está,
        # hay que invertir; --swap-hands (o la tecla 'h') corrige el resto.
        swap = cfg.swap_hands
        if not cfg.mirror:
            swap = not swap
        if swap:
            side = "R" if side == "L" else "L"
        return side

    # -- API -----------------------------------------------------------------
    def process(self, frame_bgr: np.ndarray) -> dict[str, HandPose]:
        """Procesa un frame BGR. Devuelve {side: HandPose} (vacío si no hay manos)."""
        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self._landmarker.detect_for_video(image, self._timestamp_ms())
        if not result.hand_landmarks:
            # Al perder las manos se reinicia el filtro: la reacquisición es inmediata.
            self._ema.clear()
            return {}

        poses: dict[str, HandPose] = {}
        for index, landmarks in enumerate(result.hand_landmarks):
            side = self._side(result, index, landmarks)
            raw_index = self._straightness(landmarks, INDEX_CHAIN, width, height)
            raw_middle = self._straightness(landmarks, MIDDLE_CHAIN, width, height)
            poses[side] = HandPose(
                side=side,
                index_ext=self._to_extension(raw_index, side, "index"),
                middle_ext=self._to_extension(raw_middle, side, "middle"),
                raw_index=raw_index,
                raw_middle=raw_middle,
                landmarks=landmarks,
            )

        # Descartar el suavizado de las manos que han desaparecido.
        for key in [k for k in self._ema if k[0] not in poses]:
            del self._ema[key]
        return poses

# -*- coding: utf-8 -*-
"""Reconocedor de manos basado en MediaPipe Tasks (HandLandmarker)."""

from __future__ import annotations

import contextlib
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
        # Filtro EMA independiente para la muñeca de cada mano.
        self._ema: dict[tuple[str, str], float | None] = {}

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._landmarker.close()

    # -- timestamps ------------------------------------------------------------
    def _timestamp_ms(self) -> int:
        """MediaPipe VIDEO exige timestamps estrictamente crecientes."""
        timestamp = int((time.monotonic() - self._t0) * 1000)
        if timestamp <= self._last_ts:
            timestamp = self._last_ts + 1
        self._last_ts = timestamp
        return timestamp

    @staticmethod
    def _wrist_position(wrist: Any) -> float:
        """Devuelve posición vertical normalizada: arriba +1, centro 0, abajo -1."""
        return float(max(-1.0, min(1.0, 1.0 - 2.0 * float(wrist.y))))

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

    def _side(self, result: Any, index: int, wrist: Any) -> str:
        """Traduce la etiqueta de MediaPipe a 'L'/'R' teniendo en cuenta el espejo."""
        label = self._handedness(result, index).lower()
        cfg = self._settings
        if "left" in label:
            side = "L"
        elif "right" in label:
            side = "R"
        else:
            # Sin etiqueta: en vista espejo la mano izquierda aparece a la izquierda.
            side = "L" if (wrist.x < 0.5) == cfg.mirror else "R"

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
            wrist = landmarks[0]
            side = self._side(result, index, wrist)
            raw_position = self._wrist_position(wrist)
            key = (side, "wrist")
            previous = self._ema.get(key)
            alpha = self._settings.smoothing
            position = raw_position if previous is None else alpha * raw_position + (1.0 - alpha) * previous
            self._ema[key] = position
            extension = (position + 1.0) / 2.0
            poses[side] = HandPose(
                side=side,
                index_ext=extension,
                middle_ext=1.0 - extension,
                raw_index=position,
                raw_middle=position,
                landmarks=[wrist],
            )

        # Descartar el suavizado de las manos que han desaparecido.
        for key in [k for k in self._ema if k[0] not in poses]:
            del self._ema[key]
        return poses

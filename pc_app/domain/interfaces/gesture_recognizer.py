# -*- coding: utf-8 -*-
"""Reconocedor de gestos: implementación intercambiable (MediaPipe, mocks...)."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from pc_app.domain.entities.hand_pose import HandPose


class IGestureRecognizer(ABC):
    """Convierte un frame BGR en las manos detectadas, indexadas por lado."""

    @abstractmethod
    def process(self, frame_bgr: np.ndarray) -> dict[str, HandPose]:
        """Devuelve ``{"L": HandPose, "R": HandPose}`` (vacío si no hay manos)."""

    @abstractmethod
    def close(self) -> None:
        """Libera los recursos del modelo."""

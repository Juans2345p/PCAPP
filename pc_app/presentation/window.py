# -*- coding: utf-8 -*-
"""Ventana OpenCV: mostrar frames, leer teclas y cerrar limpiamente."""

from __future__ import annotations

import contextlib

import cv2
import numpy as np

WINDOW = "Control gestual -> micro:bit"


class PreviewWindow:
    """Envoltorio mínimo de ``cv2.imshow``/``waitKey``/``destroyAllWindows``."""

    def __init__(self, title: str = WINDOW) -> None:
        self._title = title
        cv2.namedWindow(self._title, cv2.WINDOW_NORMAL)  # permite redimensionar

    def show(self, frame: np.ndarray) -> int:
        """Muestra el frame y devuelve la tecla pulsada (0xFF si no hay)."""
        cv2.imshow(self._title, frame)
        return cv2.waitKey(1) & 0xFF

    def is_open(self) -> bool:
        """``False`` si el usuario ha cerrado la ventana con la X."""
        with contextlib.suppress(cv2.error):
            return cv2.getWindowProperty(self._title, cv2.WND_PROP_VISIBLE) >= 1
        return False

    def close(self) -> None:
        with contextlib.suppress(cv2.error):
            cv2.destroyAllWindows()

# -*- coding: utf-8 -*-
"""Ventana OpenCV: mostrar frames, leer teclas y cerrar limpiamente."""

from __future__ import annotations

import contextlib

import cv2
import numpy as np

WINDOW = "Control gestual -> micro:bit"


class PreviewWindow:
    """Ventana a pantalla completa con eventos de teclado y ratón."""

    def __init__(self, title: str = WINDOW, fullscreen: bool = True) -> None:
        self._title = title
        self._fullscreen = fullscreen
        self._fullscreen_applied = False
        self._mouse_event: tuple[int, int] | None = None
        self._mouse_position: tuple[int, int] | None = None
        cv2.namedWindow(self._title, cv2.WINDOW_NORMAL)  # permite redimensionar
        cv2.setMouseCallback(self._title, self._on_mouse)

    def _set_fullscreen(self, enabled: bool) -> None:
        value = cv2.WINDOW_FULLSCREEN if enabled else cv2.WINDOW_NORMAL
        with contextlib.suppress(cv2.error):
            cv2.setWindowProperty(self._title, cv2.WND_PROP_FULLSCREEN, value)
        self._fullscreen = enabled
        self._fullscreen_applied = True

    def toggle_fullscreen(self) -> bool:
        """Alterna entre pantalla completa y ventana normal."""
        self._set_fullscreen(not self._fullscreen)
        if not self._fullscreen:
            with contextlib.suppress(cv2.error):
                cv2.resizeWindow(self._title, 1440, 900)
        return self._fullscreen

    @property
    def fullscreen(self) -> bool:
        return self._fullscreen

    def _on_mouse(self, event: int, x: int, y: int, flags: int, _userdata) -> None:
        self._mouse_position = (x, y)
        dragging = event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_LBUTTON
        if event == cv2.EVENT_LBUTTONDOWN or dragging:
            self._mouse_event = (x, y)

    def take_mouse_event(self) -> tuple[int, int] | None:
        event = self._mouse_event
        self._mouse_event = None
        return event

    @property
    def mouse_position(self) -> tuple[int, int] | None:
        return self._mouse_position

    def client_size(self, fallback: tuple[int, int] = (1440, 900)) -> tuple[int, int]:
        """Devuelve el tamaño del área de imagen de la ventana."""
        with contextlib.suppress(cv2.error):
            _x, _y, width, height = cv2.getWindowImageRect(self._title)
            if width > 0 and height > 0:
                return width, height
        return fallback

    def show(self, frame: np.ndarray) -> int:
        """Muestra el frame y devuelve la tecla pulsada (0xFF si no hay)."""
        if not self._fullscreen_applied:
            # Algunos backends de OpenCV sólo aplican fullscreen tras crear la
            # superficie de imagen con el primer imshow.
            cv2.imshow(self._title, frame)
            cv2.waitKey(1)
            self._set_fullscreen(self._fullscreen)
            cv2.waitKey(1)
        width, height = self.client_size((frame.shape[1], frame.shape[0]))
        display = frame
        if display.shape[1] != width or display.shape[0] != height:
            interpolation = (
                cv2.INTER_AREA
                if width < frame.shape[1] or height < frame.shape[0]
                else cv2.INTER_LINEAR
            )
            display = cv2.resize(display, (width, height), interpolation=interpolation)
        cv2.imshow(self._title, display)
        return cv2.waitKey(1) & 0xFF

    def is_open(self) -> bool:
        """``False`` si el usuario ha cerrado la ventana con la X."""
        with contextlib.suppress(cv2.error):
            return cv2.getWindowProperty(self._title, cv2.WND_PROP_VISIBLE) >= 1
        return False

    def close(self) -> None:
        with contextlib.suppress(cv2.error):
            cv2.destroyAllWindows()

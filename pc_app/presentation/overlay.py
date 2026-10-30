# -*- coding: utf-8 -*-
"""Dibujo del esqueleto de la mano y del panel de estado."""

from __future__ import annotations

import cv2
import numpy as np

from pc_app.config import Settings
from pc_app.domain.entities.hand_pose import HandPose
from pc_app.domain.interfaces.command_sender import ICommandSender

FONT = cv2.FONT_HERSHEY_SIMPLEX

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

SIDE_LABEL = {"L": "IZQ", "R": "DER"}
SIDE_COLOR = {"L": (0, 165, 255), "R": (0, 220, 0)}   # BGR


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def draw_hand(canvas: np.ndarray, pose: HandPose, width: int, height: int) -> None:
    """Dibuja sólo el esqueleto/vector de la mano, sin etiqueta de lado."""
    landmarks = pose.landmarks
    for start, end in HAND_CONNECTIONS:
        a, b = landmarks[start], landmarks[end]
        cv2.line(
            canvas,
            (int(a.x * width), int(a.y * height)),
            (int(b.x * width), int(b.y * height)),
            (0, 220, 0), 2, cv2.LINE_AA,
        )
    for i, lm in enumerate(landmarks):
        center = (int(lm.x * width), int(lm.y * height))
        if i in (4, 8, 12, 16, 20):  # puntas
            cv2.circle(canvas, center, 6, (0, 255, 255), -1, cv2.LINE_AA)
        else:
            cv2.circle(canvas, center, 4, (0, 0, 255), -1, cv2.LINE_AA)


def _put_right(canvas, text, x_right, y, scale=0.6,
               color=(255, 255, 255), thickness=1) -> None:
    (text_w, _), _ = cv2.getTextSize(text, FONT, scale, thickness)
    cv2.putText(canvas, text, (x_right - text_w, y), FONT, scale,
                color, thickness, cv2.LINE_AA)


def _draw_speed_bar(canvas, x, y, w, h, value, max_speed) -> None:
    """Barra bipolar centrada: izquierda = atrás, derecha = adelante."""
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (55, 55, 55), -1)
    center = x + w // 2
    fraction = _clamp(value / max(1, max_speed), -1.0, 1.0)
    length = int((w // 2) * abs(fraction))
    color = (0, 200, 0) if fraction >= 0 else (0, 140, 255)
    if length > 0:
        if fraction >= 0:
            cv2.rectangle(canvas, (center, y), (center + length, y + h), color, -1)
        else:
            cv2.rectangle(canvas, (center - length, y), (center, y + h), color, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (190, 190, 190), 1)
    cv2.line(canvas, (center, y - 2), (center, y + h + 2), (120, 120, 120), 1)


def render(
    frame: np.ndarray,
    poses: dict[str, HandPose],
    sender: ICommandSender | None,
    fps: float,
    settings: Settings,
    last_payload: str,
) -> np.ndarray:
    """Devuelve el vídeo con el esqueleto y el panel inferior de estado."""
    height, width = frame.shape[:2]
    canvas = frame.copy()
    for pose in poses.values():
        draw_hand(canvas, pose, width, height)

    panel_h = 180 if settings.debug else 160
    panel = np.full((panel_h, width, 3), 26, dtype=np.uint8)
    right = width - 16

    # --- fila 1: estado del enlace ---
    if sender is None or sender.is_dry_run:
        ble_text, ble_color = "BLE: DRY-RUN", (0, 210, 255)
    elif sender.connected:
        ble_text = f"BLE: CONECTADO (envios {sender.sent} / descartes {sender.dropped})"
        ble_color = (0, 220, 0)
    else:
        ble_text = "BLE: RECONECTANDO..."
        ble_color = (0, 0, 255)
    cv2.putText(panel, ble_text, (16, 26), FONT, 0.55, ble_color, 2, cv2.LINE_AA)
    _put_right(panel, f"CAM {fps:4.1f} FPS", right, 28, 0.55, (200, 200, 200))

    # --- filas 2 y 3: una barra por rueda ---
    bar_x = 104
    bar_w = max(100, width - bar_x - 110)
    for row, side in enumerate(("R", "L")):
        y = 42 + row * 34
        pose = poses.get(side)
        speed = pose.speed(settings.max_speed) if pose else 0.0
        color = SIDE_COLOR[side] if pose else (150, 150, 150)
        cv2.putText(panel, f"{SIDE_LABEL[side]}  motor", (16, y + 15), FONT, 0.45,
                    color, 1, cv2.LINE_AA)
        _draw_speed_bar(panel, bar_x, y, bar_w, 18, speed, settings.max_speed)
        cv2.putText(panel, f"{speed:+4.0f}", (bar_x + bar_w + 8, y + 15), FONT, 0.5,
                    color, 1, cv2.LINE_AA)

    # --- fila 4: detalle de dedos / e-stop ---
    def detail(side: str) -> str:
        pose = poses.get(side)
        if pose is None:
            return f"{SIDE_LABEL[side]} --"
        return (f"{SIDE_LABEL[side]} idx {pose.index_ext * 100:3.0f}% "
                f"med {pose.middle_ext * 100:3.0f}%")

    if poses:
        cv2.putText(panel, f"{detail('R')}     {detail('L')}", (16, 118), FONT, 0.45,
                    (215, 215, 215), 1, cv2.LINE_AA)
    else:
        cv2.putText(panel, "SIN MANOS -> E-STOP", (16, 118), FONT, 0.5,
                    (0, 0, 255), 2, cv2.LINE_AA)

    # --- fila 5: comando y ayuda ---
    cv2.putText(panel, f"CMD: {last_payload}", (16, 148), FONT, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    _put_right(panel, "q/ESC salir   h: invertir manos", right, 148, 0.45,
               (150, 150, 150))

    if settings.debug:
        raws = []
        for side in ("R", "L"):
            pose = poses.get(side)
            raws.append(
                f"{side} idx={pose.raw_index:.3f} med={pose.raw_middle:.3f}"
                if pose else f"{side} --"
            )
        cv2.putText(panel, "   ".join(raws), (16, 172), FONT, 0.45, (150, 150, 150),
                    1, cv2.LINE_AA)

    return np.vstack([canvas, panel])

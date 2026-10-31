# -*- coding: utf-8 -*-
"""Renderizado de la UI de escritorio a partir del diseño pen.dev.

Dibuja las dos pantallas del diseño (En vivo y Configuración) como un
dashboard de 1440x900 con la webcam en el escenario principal y la
telemetría/controles en la barra lateral derecha. Los colores y métricas se
toman de ``pc_app.infrastructure.pen_ui_loader``.
"""

from __future__ import annotations

import cv2
import numpy as np

from pc_app.config import Settings
from pc_app.domain.entities.hand_pose import HandPose
from pc_app.domain.interfaces.command_sender import ICommandSender
from pc_app.infrastructure.pen_ui_loader import get_design

# ---------------------------------------------------------------------------
# Tema y métricas (resueltos desde el diseño)
# ---------------------------------------------------------------------------
_DESIGN = get_design()
_T = _DESIGN.theme
W = _T.window_width
H = _T.window_height
TOP_H = _T.top_bar_height
SIDE_W = _T.sidebar_width
PAD = 0

BG = _T.color("bg")
SURFACE = _T.color("surface")
BORDER = _T.color("border")
BORDER_STRONG = _T.color("border-strong")
TEXT_PRIMARY = _T.color("text-primary")
TEXT_SECONDARY = _T.color("text-secondary")
TEXT_MUTED = _T.color("text-muted")
ACCENT = _T.color("accent")
DANGER = _T.color("danger")
INPUT = _T.color("input")
SEGMENT_OFF = _T.color("segment-off")
INSTITUTIONAL_RED = (38, 31, 210)
_focused_field: str | None = None
_input_buffer = ""
_input_select_all = False

FONT = cv2.FONT_HERSHEY_SIMPLEX
def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def _pose_speed(pose, settings):
    if pose is None:
        return 0.0
    return pose.speed(
        settings.max_speed, settings.deadzone, settings.speed_multiplier
    )


def _round_rect(img, x, y, w, h, r, color, thickness=-1):
    r = max(1, min(r, w // 2, h // 2))
    if thickness < 0:
        cv2.rectangle(img, (x + r, y), (x + w - r, y + h), color, -1)
        cv2.rectangle(img, (x, y + r), (x + w, y + h - r), color, -1)
        for cx, cy in ((x + r, y + r), (x + w - r, y + r),
                       (x + r, y + h - r), (x + w - r, y + h - r)):
            cv2.circle(img, (cx, cy), r, color, -1, cv2.LINE_AA)
    else:
        cv2.rectangle(img, (x + r, y), (x + w - r, y + h), color, thickness)
        cv2.rectangle(img, (x, y + r), (x + w, y + h - r), color, thickness)
        for cx, cy in ((x + r, y + r), (x + w - r, y + r),
                       (x + r, y + h - r), (x + w - r, y + h - r)):
            cv2.circle(img, (cx, cy), r, color, thickness, cv2.LINE_AA)


def _text(img, text, x, y, scale=0.5, color=TEXT_PRIMARY, thickness=1,
          font=FONT, align="left"):
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    xx = x
    if align == "right":
        xx = x - tw
    elif align == "center":
        xx = x - tw // 2
    cv2.putText(img, text, (xx, y), font, scale, color, thickness, cv2.LINE_AA)
    return tw, th


def _pill(img, x, y, w, h, color, r=999):
    _round_rect(img, x, y, w, h, min(r, h // 2), color, -1)


def _draw_hand_icon(canvas, x, y):
    points = np.array([
        [x + 4, y + 12], [x + 4, y + 9], [x + 7, y + 9],
        [x + 7, y + 3], [x + 10, y + 3], [x + 10, y + 8],
        [x + 12, y + 1], [x + 15, y + 2], [x + 14, y + 9],
        [x + 16, y + 5], [x + 19, y + 6], [x + 17, y + 12],
        [x + 15, y + 17], [x + 8, y + 17],
    ], dtype=np.int32)
    cv2.polylines(canvas, [points], True, (255, 255, 255), 2, cv2.LINE_AA)


def _top_bar(canvas, ble_connected, dry_run, device_addr, running=True):
    cv2.rectangle(canvas, (0, 0), (W, TOP_H), SURFACE, -1)
    cv2.line(canvas, (0, TOP_H), (W, TOP_H), BORDER, 1)
    _round_rect(canvas, 28, 15, 34, 34, 8, INSTITUTIONAL_RED, -1)
    _draw_hand_icon(canvas, 36, 22)
    _text(canvas, "UNIVERSIDAD DEL TOLIMA", 74, 27, 0.29, TEXT_MUTED, 1)
    _text(canvas, "Carrito micro:bit · Control gestual", 74, 44, 0.42, TEXT_PRIMARY, 1)

    _keycap(canvas, "H", 596, 20)
    _text(canvas, "invertir manos", 620, 35, 0.32, TEXT_MUTED, 1)
    _keycap(canvas, "Q / ESC", 712, 20, 52)
    _text(canvas, "salir", 770, 35, 0.32, TEXT_MUTED, 1)

    right = W - 28
    switch_x, switch_y = right - 42, 20
    run_color = _rgb_hex("#007A33") if running else BORDER_STRONG
    _round_rect(canvas, switch_x, switch_y, 42, 24, 999, run_color, -1)
    cv2.circle(canvas, (switch_x + (30 if running else 12), switch_y + 12),
               9, (255, 255, 255), -1, cv2.LINE_AA)
    _text(canvas, "EN MARCHA" if running else "PAUSADO", switch_x - 10, 35,
          0.3, _rgb_hex("#007A33") if running else DANGER, 1, align="right")
    divider_x = switch_x - 80
    cv2.line(canvas, (divider_x, 22), (divider_x, 42), BORDER, 1)
    mac_right = divider_x - 14
    _text(canvas, device_addr, mac_right, 35, 0.3, TEXT_MUTED, 1, align="right")
    mac_width = cv2.getTextSize(device_addr, FONT, 0.3, 1)[0][0]
    badge_right = mac_right - mac_width - 18
    badge = "DRY-RUN" if dry_run else ("BLE CONECTADO" if ble_connected else "BLE RECONECTANDO")
    badge_color = _rgb_hex("#007A33") if (ble_connected or dry_run) else DANGER
    badge_width = cv2.getTextSize(badge, FONT, 0.31, 1)[0][0]
    _pill(canvas, badge_right - badge_width - 20, 23, badge_width + 14, 19,
          _rgb_hex("#E8F4EC") if (ble_connected or dry_run) else (251, 236, 236), 999)
    cv2.circle(canvas, (badge_right - badge_width - 12, 32), 3, badge_color, -1, cv2.LINE_AA)
    _text(canvas, badge, badge_right - 7, 36, 0.31, TEXT_SECONDARY, 1, align="right")


def _rgb_hex(hex_value):
    value = hex_value.lstrip("#")
    return (int(value[4:6], 16), int(value[2:4], 16), int(value[0:2], 16))


SOFT_SURFACE = _rgb_hex("#F2F2F0")


def _keycap(canvas, text, x, y, width=None):
    width = width or max(18, cv2.getTextSize(text, FONT, 0.27, 1)[0][0] + 10)
    _round_rect(canvas, x, y, width, 22, 5, INPUT, -1)
    cv2.rectangle(canvas, (x, y), (x + width, y + 22), BORDER, 1)
    _text(canvas, text, x + width // 2, y + 15, 0.27, TEXT_PRIMARY, 1, align="center")


def _blend_region(canvas, x1, y1, x2, y2, color, alpha):
    if x2 <= x1 or y2 <= y1:
        return
    region = canvas[y1:y2, x1:x2]
    tint = np.empty_like(region)
    tint[:] = color
    cv2.addWeighted(tint, alpha, region, 1.0 - alpha, 0, region)


def _camera_stage(canvas, frame, poses, fps, settings, x, y, w, h):
    stage = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
    canvas[y:y + h, x:x + w] = stage
    header_h = 50
    _blend_region(canvas, x, y, x + w, y + header_h, (255, 255, 255), 0.08)
    cv2.line(canvas, (x, y + header_h), (x + w, y + header_h), _rgb_hex("#007A33"), 1)
    cv2.circle(canvas, (x + 22, y + 25), 3, DANGER, -1, cv2.LINE_AA)
    _text(canvas, "EN VIVO", x + 36, y + 29, 0.37, (255, 255, 255), 1)
    _text(canvas, f"cámara {settings.camera}", x + 108, y + 29, 0.32,
          (102, 102, 102), 1)
    _text(canvas, f"{fps:4.0f} fps", x + w - 22, y + 29, 0.32,
          (102, 102, 102), 1, align="right")

    middle_x = x + w // 2
    labels_y = y + header_h + 34
    _blend_region(canvas, middle_x, y + header_h, middle_x + 1, y + h,
                  (255, 255, 255), 0.24)
    cv2.circle(canvas, (x + 27, labels_y - 4), 2, _rgb_hex("#5FD08A"), -1, cv2.LINE_AA)
    _text(canvas, "MANO IZQUIERDA", x + 36, labels_y, 0.29, (153, 153, 153), 1)
    cv2.circle(canvas, (middle_x + 27, labels_y - 4), 2, (77, 77, 77), -1, cv2.LINE_AA)
    _text(canvas, "MANO DERECHA", middle_x + 36, labels_y, 0.29, (153, 153, 153), 1)

    neutral_h = min(h - header_h - 4, int(h * max(0.0, min(0.99, settings.deadzone))))
    center_y = y + h // 2
    band_top = center_y - neutral_h // 2
    band_bottom = band_top + neutral_h
    left_x2 = x + w // 2
    top_of_zones = y + header_h + 34
    zones = ((top_of_zones, band_top), (band_top, band_bottom),
             (band_bottom, y + h))
    for zone_top, zone_bottom in zones:
        _blend_region(canvas, x, zone_top, left_x2, zone_bottom, (255, 255, 255), 0.24)
        _blend_region(canvas, left_x2, zone_top, x + w, zone_bottom, (0, 0, 0), 0.20)
    for line_y in (band_top, band_bottom):
        _blend_region(canvas, x, line_y, x + w, line_y + 1, (255, 255, 255), 0.24)

    forward_room = band_top - (y + header_h)
    if forward_room >= 24:
        forward_label_y = min(y + header_h + 52, band_top - 8)
        _text(canvas, "ADELANTE", x + 24, forward_label_y, 0.36,
              _rgb_hex("#5FD08A"), 1)
        if forward_room >= 40:
            _text(canvas, "acelera", x + 24, forward_label_y + 15, 0.25,
                  (89, 89, 89), 1)
    if neutral_h >= 18:
        _text(canvas, "STOP", x + 24, center_y + 4, 0.34, (153, 153, 153), 1)
        _text(canvas, "zona neutra", x + 74, center_y + 4,
              0.29, (89, 89, 89), 1)
    backward_room = y + h - band_bottom
    if backward_room >= 24:
        backward_label_y = min(y + h - 18, band_bottom + 28)
        _text(canvas, "ATRÁS", x + 24, backward_label_y, 0.36,
              _rgb_hex("#D99A3C"), 1)
        if backward_room >= 40:
            _text(canvas, "retrocede", x + 24, backward_label_y + 15, 0.25,
                  (89, 89, 89), 1)

    for side, pose in poses.items():
        if pose.landmarks:
            wrist = pose.landmarks[0]
            cx, cy = int(wrist.x * w), int(wrist.y * h)
            cv2.circle(canvas, (x + cx, y + cy), 14, (179, 179, 179), 1, cv2.LINE_AA)
            cv2.circle(canvas, (x + cx, y + cy), 4, (255, 255, 255), -1, cv2.LINE_AA)
            _text(canvas, "muñeca", x + cx + 18, y + cy + 4, 0.25,
                  (140, 140, 140), 1)



def render(
    frame: np.ndarray,
    poses: dict[str, HandPose],
    sender: ICommandSender | None,
    fps: float,
    settings: Settings,
    last_payload: str,
    panel=None,
    running: bool = True,
    hover: tuple[int, int] | None = None,
) -> np.ndarray:
    """Devuelve el dashboard completo según las dimensiones del diseño."""
    canvas = np.full((H, W, 3), BG, dtype=np.uint8)

    # top bar
    dry_run = bool(getattr(sender, "is_dry_run", False)) if sender is not None else False
    ble_connected = bool(getattr(sender, "connected", False)) if sender is not None else False
    addr = settings.address if (panel is None) else (panel.state.ble_address)
    _top_bar(canvas, ble_connected, dry_run, addr, running)

    stage_x = 0
    stage_y = TOP_H
    stage_w = W - SIDE_W
    stage_h = H - TOP_H
    _camera_stage(canvas, frame, poses, fps, settings, stage_x, stage_y, stage_w, stage_h)
    _sidebar_live(
        canvas, stage_w, stage_y, SIDE_W, stage_h, sender, settings,
        poses, last_payload, panel, running, hover,
    )

    return canvas



def _sidebar_live(canvas, x, y, w, h, sender, settings, poses, last_payload,
                  panel=None, running=True, hover=None):
    cv2.rectangle(canvas, (x, y), (x + w, y + h), SURFACE, -1)
    cv2.line(canvas, (x, y), (x, y + h), BORDER, 1)
    content_x = x + 22
    _text(canvas, "RUEDAS", content_x, y + 42, 0.32, TEXT_MUTED, 1)
    card_y = y + 54
    _wheel_tile(canvas, content_x, card_y, 153, 164, "L", poses, settings)
    _wheel_tile(canvas, content_x + 169, card_y, 153, 164, "R", poses, settings)

    state_top = y + 234
    _text(canvas, "ESTADO", content_x, state_top + 20, 0.32, TEXT_MUTED, 1)
    if not running:
        status, detail = "Control pausado", "Parada inmediata enviada al carro."
        fill, edge, ink = _rgb_hex("#FDF3F3"), INSTITUTIONAL_RED, INSTITUTIONAL_RED
    elif len(poses) >= 2:
        status, detail = "Dos manos detectadas", "Seguimiento activo · control por rueda."
        fill, edge, ink = _rgb_hex("#E8F4EC"), _rgb_hex("#B8DCC4"), _rgb_hex("#007A33")
    elif len(poses) == 1:
        status, detail = "Falta una mano", "La otra rueda queda en cero."
        fill, edge, ink = _rgb_hex("#FCF3E2"), _rgb_hex("#E5C994"), _rgb_hex("#A96500")
    else:
        status, detail = "Faltan las dos manos", "Carro detenido · sin envío por BLE."
        fill, edge, ink = _rgb_hex("#FDF3F3"), INSTITUTIONAL_RED, INSTITUTIONAL_RED
    alert_y, alert_h = state_top + 48, 75
    _round_rect(canvas, content_x, alert_y, 322, alert_h, 12, fill, -1)
    cv2.rectangle(canvas, (content_x, alert_y), (content_x + 322, alert_y + alert_h), edge, 1)
    cv2.circle(canvas, (content_x + 21, alert_y + 24), 8, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(canvas, (content_x + 21, alert_y + 24), 7, ink, 1, cv2.LINE_AA)
    _text(canvas, "!", content_x + 21, alert_y + 28, 0.32, ink, 1, align="center")
    _text(canvas, status, content_x + 40, alert_y + 26, 0.34, ink, 1)
    _text(canvas, detail, content_x + 40, alert_y + 47, 0.27, TEXT_SECONDARY, 1)

    config_y = y + 550
    _text(canvas, "CONFIGURACIÓN", content_x, config_y, 0.32, TEXT_MUTED, 1)
    state = panel.state if panel is not None else None
    fields = [
        ("deadzone", "ZONA STOP", state.deadzone if state else settings.deadzone,
         f"{round((state.deadzone if state else settings.deadzone) * 100):d}", "% alto"),
        ("smoothing", "SUAVIZADO", state.smoothing if state else settings.smoothing,
         f"{(state.smoothing if state else settings.smoothing):.2f}", "EMA"),
        ("step", "PASO", state.step if state else settings.step,
         f"{state.step if state else settings.step}", ""),
        ("lost_grace", "PÉRDIDA", state.lost_grace if state else settings.lost_grace,
         f"{(state.lost_grace if state else settings.lost_grace):.2f}", "s"),
    ]
    cfg_x, cfg_y = content_x, y + 562
    slider_x, slider_top, slider_bottom = cfg_x + 27, cfg_y + 34, cfg_y + 234
    cv2.line(canvas, (slider_x, slider_top), (slider_x, slider_bottom), SEGMENT_OFF, 2)
    multiplier = state.speed_multiplier if state else settings.speed_multiplier
    mult_y = int(slider_bottom - _clamp(multiplier / 1.5, 0, 1) * (slider_bottom - slider_top))
    cv2.line(canvas, (slider_x, slider_bottom), (slider_x, mult_y), INSTITUTIONAL_RED, 2)
    cv2.circle(canvas, (slider_x, mult_y), 12, INSTITUTIONAL_RED, -1, cv2.LINE_AA)
    cv2.circle(canvas, (slider_x, mult_y), 5, (255, 255, 255), -1, cv2.LINE_AA)
    _text(canvas, "×1.5", slider_x, cfg_y + 24, 0.25, TEXT_MUTED, 1, align="center")
    _text(canvas, "×0.0", slider_x, slider_bottom + 16, 0.25, TEXT_MUTED, 1, align="center")
    _text(canvas, f"×{multiplier:.2f}", slider_x + 18, mult_y + 4, 0.28, TEXT_PRIMARY, 1)

    field_x, field_w = cfg_x + 71, 242
    info_points = {}
    help_text = {
        "deadzone": "Porcentaje de altura central que queda en STOP. Dentro de esa franja la rueda recibe velocidad cero.",
        "smoothing": "Suaviza el movimiento de la muñeca. Alto responde rápido con más ruido; bajo es más estable y añade retardo.",
        "step": "Redondea la velocidad en incrementos y define el cambio mínimo para enviar otra orden al motor.",
        "lost_grace": "Segundos que se conserva la última posición cuando se pierde una mano antes de poner su rueda en cero.",
    }
    for i, (key, label, _value, display, unit) in enumerate(fields):
        top = cfg_y + 12 + i * 63
        _text(canvas, label, field_x, top + 8, 0.23, TEXT_MUTED, 1)
        label_width = cv2.getTextSize(label, FONT, 0.23, 1)[0][0]
        info_x, info_y = field_x + label_width + 9, top + 4
        info_points[key] = (info_x, info_y)
        cv2.circle(canvas, (info_x, info_y), 6, _rgb_hex("#F2F2F0"), -1, cv2.LINE_AA)
        cv2.circle(canvas, (info_x, info_y), 6, _rgb_hex("#D8D8D4"), 1, cv2.LINE_AA)
        _text(canvas, "i", info_x, info_y + 3, 0.22, TEXT_SECONDARY, 1, align="center")
        box_y = top + 14
        focused = _focused_field == key
        _round_rect(canvas, field_x, box_y, field_w, 36, 8, INPUT, -1)
        cv2.rectangle(canvas, (field_x, box_y), (field_x + field_w, box_y + 36),
                      INSTITUTIONAL_RED if focused else _rgb_hex("#D8D8D4"), 1)
        value_text = _input_buffer if focused else display
        _text(canvas, value_text + ("_" if focused else ""), field_x + 10,
              box_y + 23, 0.32, TEXT_PRIMARY, 1)
        _text(canvas, unit, field_x + field_w - 10, box_y + 22,
              0.23, TEXT_MUTED, 1, align="right")

    if hover is not None:
        active = next((key for key, (ix, iy) in info_points.items()
                       if (hover[0] - ix) ** 2 + (hover[1] - iy) ** 2 <= 11 ** 2), None)
        if active is not None:
            title = next(label for key, label, *_ in fields if key == active)
            lines = _wrap_text(help_text[active], 230, 0.27)
            tip_w, tip_h = 252, 26 + len(lines) * 14 + 8
            tip_x = min(max(x + 8, hover[0] + 12), W - tip_w - 8)
            tip_y = min(max(TOP_H + 8, hover[1] + 12), H - tip_h - 8)
            _round_rect(canvas, tip_x, tip_y, tip_w, tip_h, 7, TEXT_PRIMARY, -1)
            cv2.rectangle(canvas, (tip_x, tip_y), (tip_x + tip_w, tip_y + tip_h),
                          _rgb_hex("#D8D8D4"), 1)
            _text(canvas, title, tip_x + 10, tip_y + 16, 0.28,
                  (255, 255, 255), 1)
            for line_no, line in enumerate(lines):
                _text(canvas, line, tip_x + 10, tip_y + 30 + line_no * 14,
                      0.25, (235, 235, 235), 1)


def _wrap_text(text, max_width, scale):
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and cv2.getTextSize(candidate, FONT, scale, 1)[0][0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _wheel_tile(canvas, x, y, w, h, side, poses, settings):
    _round_rect(canvas, x, y, w, h, 12, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), BORDER, 1)
    pose = poses.get(side)
    speed = _pose_speed(pose, settings)
    name = "IZQUIERDA" if side == "L" else "DERECHA"
    _text(canvas, name, x + 16, y + 28, 0.27, TEXT_SECONDARY, 1)
    direction = "ADELANTE" if speed > 0 else ("ATRÁS" if speed < 0 else "DETENIDO")
    arrow_color = (_rgb_hex("#007A33") if speed > 0 else
                   _rgb_hex("#D99A3C") if speed < 0 else TEXT_MUTED)
    _text(canvas, direction, x + 16, y + 58, 0.31, arrow_color, 1)
    arrow_start = (x + w - 34, y + 49)
    if speed > 0:
        arrow_end = (x + w - 34, y + 31)
    elif speed < 0:
        arrow_end = (x + w - 34, y + 67)
    else:
        arrow_end = (x + w - 18, y + 49)
    cv2.arrowedLine(canvas, arrow_start, arrow_end, arrow_color, 2,
                    cv2.LINE_AA, tipLength=0.35)
    cv2.line(canvas, (x + 16, y + 73), (x + w - 16, y + 73), _rgb_hex("#EDEDE9"), 1)
    sent = int(round(speed))
    _text(canvas, "ENVÍO", x + 16, y + 94, 0.23, _rgb_hex("#B0B0AB"), 1)
    _text(canvas, f"{sent:+d}/{settings.max_speed}", x + w - 16, y + 94,
          0.3, _rgb_hex("#6B6B66"), 1, align="right")
    bar_x, bar_y, bar_w = x + 16, y + 111, w - 32
    cv2.line(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y), SOFT_SURFACE, 3, cv2.LINE_AA)
    fill_w = int(bar_w * _clamp(abs(speed) / max(1, settings.max_speed), 0, 1))
    if fill_w:
        cv2.line(canvas, (bar_x, bar_y), (bar_x + fill_w, bar_y), arrow_color, 3, cv2.LINE_AA)
    chip_y = y + 130
    _round_rect(canvas, x + 16, chip_y, w - 32, 24, 999, SOFT_SURFACE, -1)
    dot_color = _rgb_hex("#007A33") if pose else _rgb_hex("#B0B0AB")
    cv2.circle(canvas, (x + 28, chip_y + 12), 4, dot_color, -1, cv2.LINE_AA)
    _text(canvas, "MANO DETECTADA" if pose else "SIN MANO",
          x + 38, chip_y + 16, 0.22, dot_color, 1)


def _field_text(panel, key):
    state = panel.state
    if key == "deadzone":
        return str(round(state.deadzone * 100))
    if key == "smoothing":
        return f"{state.smoothing:.2f}"
    if key == "step":
        return str(state.step)
    return f"{state.lost_grace:.2f}"


def _commit_input(panel):
    global _focused_field, _input_buffer, _input_select_all
    if _focused_field is None or panel is None:
        return True
    field, text = _focused_field, _input_buffer.strip()
    try:
        if field == "deadzone":
            value = float(text) / 100.0
            if not 0.0 <= value < 1.0:
                raise ValueError("ZONA STOP debe estar entre 0 y 99 %")
            panel.set_deadzone(value)
        elif field == "smoothing":
            value = float(text)
            if not 0.0 < value <= 1.0:
                raise ValueError("SUAVIZADO debe estar en (0, 1]")
            panel.set_smoothing(value)
        elif field == "step":
            value = int(text)
            if value < 1:
                raise ValueError("PASO debe ser mayor que cero")
            panel.set_step(value)
        else:
            value = float(text)
            if value < 0.0:
                raise ValueError("PÉRDIDA no puede ser negativa")
            panel.set_lost_grace(value)
    except (ValueError, TypeError, SystemExit):
        _focused_field = None
        _input_buffer = ""
        _input_select_all = False
        return False
    _focused_field = None
    _input_buffer = ""
    _input_select_all = False
    return True


def handle_mouse(x, y, panel, controller=None):
    """Procesa el switch, los cuatro inputs y el slider del diseño."""
    global _focused_field, _input_buffer, _input_select_all
    if panel is None:
        return False
    if _focused_field is not None and not _commit_input(panel):
        return False
    if y <= 48 and W - 70 <= x <= W - 18 and controller is not None:
        _focused_field = None
        controller.set_enabled(not controller.enabled)
        return True

    config_x = W - SIDE_W + 22
    cfg_y = TOP_H + 562
    field_x, field_w = config_x + 71, 242
    fields = ("deadzone", "smoothing", "step", "lost_grace")
    for i, key in enumerate(fields):
        box_y = cfg_y + 12 + i * 63 + 14
        if field_x <= x <= field_x + field_w and box_y <= y <= box_y + 36:
            _focused_field = key
            _input_buffer = _field_text(panel, key)
            _input_select_all = True
            return True

    slider_x = config_x + 27
    slider_top, slider_bottom = cfg_y + 34, cfg_y + 234
    if abs(x - slider_x) <= 18 and slider_top <= y <= slider_bottom:
        fraction = 1.0 - (y - slider_top) / max(1, slider_bottom - slider_top)
        value = round(_clamp(fraction, 0.0, 1.0) * 1.5, 2)
        if value != panel.state.speed_multiplier:
            panel.set_speed_multiplier(value)
        _focused_field = None
        _input_select_all = False
        return True

    _focused_field = None
    _input_select_all = False
    return False


def handle_key(key, panel):
    """Edita y confirma el input enfocado; guardar ocurre al pulsar Enter."""
    global _focused_field, _input_buffer, _input_select_all
    if _focused_field is None or panel is None:
        return False
    if key in (10, 13):
        _commit_input(panel)
        return True
    if key in (8, 127):
        _input_buffer = "" if _input_select_all else _input_buffer[:-1]
        _input_select_all = False
        return True
    if 48 <= key <= 57 or (key == 46 and _focused_field != "step"):
        if _input_select_all:
            _input_buffer = ""
            _input_select_all = False
        if len(_input_buffer) < 7:
            _input_buffer += chr(key)
        return True
    return True

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
PAD = 28

BG = _T.color("bg")
SURFACE = _T.color("surface")
SURFACE_RAISED = _T.color("surface-raised")
BORDER = _T.color("border")
BORDER_STRONG = _T.color("border-strong")
TEXT_PRIMARY = _T.color("text-primary")
TEXT_SECONDARY = _T.color("text-secondary")
TEXT_MUTED = _T.color("text-muted")
ACCENT = _T.color("accent")
ACCENT_DIM = _T.color("accent-dim")
WHEEL_LEFT = _T.color("wheel-left")
WHEEL_RIGHT = _T.color("wheel-right")
DANGER = _T.color("danger")
INPUT = _T.color("input")
ON_ACCENT = _T.color("on-accent")
SEGMENT_OFF = _T.color("segment-off")

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_DUPLEX = cv2.FONT_HERSHEY_DUPLEX

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

SIDE_LABEL = {"L": "IZQ", "R": "DER"}
SIDE_COLOR = {"L": WHEEL_LEFT, "R": WHEEL_RIGHT}


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


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


def draw_hand(canvas, pose, width, height):
    landmarks = pose.landmarks
    for start, end in HAND_CONNECTIONS:
        a, b = landmarks[start], landmarks[end]
        cv2.line(
            canvas,
            (int(a.x * width), int(a.y * height)),
            (int(b.x * width), int(b.y * height)),
            ACCENT, 2, cv2.LINE_AA,
        )
    for i, lm in enumerate(landmarks):
        center = (int(lm.x * width), int(lm.y * height))
        if i in (4, 8, 12, 16, 20):
            cv2.circle(canvas, center, 6, ACCENT, -1, cv2.LINE_AA)
        else:
            cv2.circle(canvas, center, 3, (11, 21, 18), -1, cv2.LINE_AA)
            cv2.circle(canvas, center, 3, ACCENT, 1, cv2.LINE_AA)


def _top_bar(canvas, active_tab, ble_connected, dry_run, device_addr):
    cv2.rectangle(canvas, (0, 0), (W, TOP_H), SURFACE, -1)
    cv2.line(canvas, (0, TOP_H), (W, TOP_H), BORDER, 1)

    # Brand
    _round_rect(canvas, 30, (TOP_H - 36) // 2, 36, 36, 8, ACCENT_DIM, -1)
    cv2.rectangle(canvas, (30, (TOP_H - 36) // 2), (66, (TOP_H - 36) // 2 + 36),
                  BORDER_STRONG, 1)
    _text(canvas, "G", 42, (TOP_H // 2) + 6, 0.7, ACCENT, 2, align="center")
    _text(canvas, "GESTO", 78, TOP_H // 2 - 2, 0.6, TEXT_PRIMARY, 1)
    _text(canvas, "CAR CONTROL", 78, TOP_H // 2 + 12, 0.35, TEXT_MUTED, 1)

    # Tabs
    tabs = ["EN VIVO", "CALIBRACIÓN", "AJUSTES"]
    tab_x = 260
    for t in tabs:
        active = (t == active_tab)
        fill = ACCENT_DIM if active else (0, 0, 0, 0)
        # transparent inactive: draw faint surface
        if not active:
            fill = (0, 0, 0)
        tw, _ = cv2.getTextSize(t, FONT, 0.4, 1)[0]
        bw = tw + 28
        bh = 28
        by = (TOP_H - bh) // 2
        if active:
            _round_rect(canvas, tab_x, by, bw, bh, 6, ACCENT_DIM, -1)
        else:
            _round_rect(canvas, tab_x, by, bw, bh, 6, SURFACE_RAISED, -1)
        color = ACCENT if active else TEXT_MUTED
        _text(canvas, t, tab_x + 14, by + 18, 0.4, color, 1)
        tab_x += bw + 4

    # BLE status (right side)
    rx = W - 30
    # device address
    _text(canvas, device_addr, rx, TOP_H // 2 + 4, 0.4, TEXT_MUTED, 1, align="right")
    rx -= cv2.getTextSize(device_addr, FONT, 0.4, 1)[0][0] + 14
    # badge
    badge_text = "DRY-RUN" if dry_run else ("CONECTADO" if ble_connected else "RECONECTANDO")
    badge_color = ACCENT if (ble_connected or dry_run) else DANGER
    bt = badge_text
    btw, _ = cv2.getTextSize(bt, FONT, 0.4, 1)[0]
    bw = btw + 24
    bh = 22
    by = (TOP_H - bh) // 2
    bx = rx - bw
    _round_rect(canvas, bx, by, bw, bh, 999, (210, 205, 255), -1)
    cv2.circle(canvas, (bx + 10, by + bh // 2), 3, badge_color, -1, cv2.LINE_AA)
    _text(canvas, bt, bx + 18, by + 15, 0.4, (50, 30, 30) if badge_color == ACCENT else DANGER, 1)
    rx = bx - 14
    # icon buttons
    for _ in range(2):
        _round_rect(canvas, rx - 34, (TOP_H - 34) // 2, 34, 34, 8, SURFACE_RAISED, -1)
        cv2.rectangle(canvas, (rx - 34, (TOP_H - 34) // 2),
                      (rx, (TOP_H - 34) // 2 + 34), BORDER, 1)
        rx -= 40


def _camera_stage(canvas, frame, poses, fps, settings, x, y, w, h):
    # background
    _round_rect(canvas, x, y, w, h, 12, INPUT, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), BORDER, 1)

    # resize frame to stage
    stage = cv2.resize(frame, (w, h))
    # draw skeleton on stage
    for pose in poses.values():
        draw_hand(stage, pose, w, h)
    canvas[y:y + h, x:x + w] = stage

    # grid overlay (subtle)
    # top overlay bar
    _round_rect(canvas, x + 22, y + 20, w - 44, 30, 999, (210, 205, 255), -1)
    # live badge
    badge_x = x + 22 + 8
    badge_y = y + 20 + 5
    _round_rect(canvas, badge_x, badge_y, 70, 20, 999, (210, 205, 255), -1)
    cv2.circle(canvas, (badge_x + 10, badge_y + 10), 3, DANGER, -1, cv2.LINE_AA)
    _text(canvas, "EN VIVO", badge_x + 18, badge_y + 14, 0.35, (50, 30, 30), 1)
    _text(canvas, f"CAM 0 · {settings.width} × {settings.height}",
          badge_x + 80, badge_y + 14, 0.4, TEXT_SECONDARY, 1)
    # fps right
    fps_text = f"{fps:4.1f} FPS"
    _text(canvas, fps_text, x + w - 30, badge_y + 14, 0.4, ACCENT, 1, align="right")
    _text(canvas, "h: invertir manos", x + w - 30, badge_y + 14 + 0, 0.4, TEXT_MUTED, 1, align="right")
    # move mirror hint below fps? keep right-aligned same line shifted
    # hands counter bottom-left
    _round_rect(canvas, x + 22, y + h - 46, 200, 28, 6, (240, 240, 240), -1)
    cv2.rectangle(canvas, (x + 22, y + h - 46), (x + 222, y + h - 18), BORDER, 1)
    hands = len(poses)
    status = "SIGUIENDO" if hands > 0 else "SIN MANOS"
    _text(canvas, f"MANOS {hands} / {settings.num_hands} · {status}",
          x + 34, y + h - 26, 0.35, TEXT_SECONDARY, 1)
    # tracking note bottom-right
    _text(canvas, "SEGUIMIENTO DE 21 PUNTOS", x + w - 30, y + h - 26, 0.35,
          TEXT_MUTED, 1, align="right")


def _legend_bar(canvas, x, y, w, h):
    _round_rect(canvas, x, y, w, h, 10, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), BORDER, 1)
    items = [("ÍNDICE", "Avanzar", ACCENT),
             ("MEDIO", "Retroceder", WHEEL_LEFT),
             ("PUÑO", "Parar", DANGER)]
    ix = x + 18
    for label, action, color in items:
        # icon box
        _round_rect(canvas, ix, y + (h - 28) // 2, 28, 28, 6, SURFACE_RAISED, -1)
        cv2.rectangle(canvas, (ix, y + (h - 28) // 2),
                      (ix + 28, y + (h - 28) // 2 + 28), BORDER, 1)
        _text(canvas, label[0], ix + 10, y + h // 2 + 4, 0.45, color, 1)
        _text(canvas, label, ix + 36, y + (h // 2) - 6, 0.3, TEXT_MUTED, 1)
        _text(canvas, action, ix + 36, y + (h // 2) + 10, 0.4, TEXT_SECONDARY, 1)
        ix += 150
    # keyboard hints right
    hx = x + w - 18
    # H key
    _text(canvas, "invertir manos", hx, y + h // 2 + 4, 0.35, TEXT_MUTED, 1, align="right")
    _round_rect(canvas, hx - 140, y + (h - 20) // 2, 18, 20, 4, SURFACE_RAISED, -1)
    _text(canvas, "H", hx - 131, y + h // 2 + 4, 0.35, TEXT_SECONDARY, 1)
    _text(canvas, "salir", hx - 170, y + h // 2 + 4, 0.35, TEXT_MUTED, 1, align="right")
    _round_rect(canvas, hx - 230, y + (h - 20) // 2, 46, 20, 4, SURFACE_RAISED, -1)
    _text(canvas, "Q/ESC", hx - 207, y + h // 2 + 4, 0.3, TEXT_SECONDARY, 1)


def _ble_card(canvas, x, y, w, sender, settings, poses):
    card_h = 170
    _round_rect(canvas, x, y, w, card_h, 12, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + card_h), BORDER, 1)
    # header
    _text(canvas, "ENLACE BLE", x + 18, y + 24, 0.35, TEXT_MUTED, 1)
    # badge
    if sender is None or sender.is_dry_run:
        badge_text = "DRY-RUN"
        badge_col = ACCENT
        dot_col = ACCENT
    elif sender.connected:
        badge_text = "CONECTADO"
        badge_col = (50, 30, 30)
        dot_col = ACCENT
    else:
        badge_text = "RECONECTANDO"
        badge_col = DANGER
        dot_col = DANGER
    bw = 110
    _round_rect(canvas, x + w - bw - 18, y + 10, bw, 20, 999, (210, 205, 255), -1)
    cv2.circle(canvas, (x + w - bw - 8, y + 20), 3, dot_col, -1, cv2.LINE_AA)
    _text(canvas, badge_text, x + w - bw + 4, y + 24, 0.35, badge_col, 1)
    # device row
    dy = y + 46
    _round_rect(canvas, x + 18, dy, 34, 34, 8, ACCENT_DIM, -1)
    cv2.rectangle(canvas, (x + 18, dy), (x + 52, dy + 34), BORDER, 1)
    _text(canvas, "B", x + 35, dy + 22, 0.6, ACCENT, 1, align="center")
    name = settings.name or "BBC micro:bit"
    _text(canvas, name, x + 60, dy + 16, 0.55, TEXT_PRIMARY, 1)
    addr = settings.address
    _text(canvas, addr, x + 60, dy + 32, 0.35, TEXT_MUTED, 1)
    # divider
    cv2.line(canvas, (x + 18, dy + 46), (x + w - 18, dy + 46), BORDER, 1)
    # metrics
    my = dy + 60
    metrics = [("ESCRITURAS", str(getattr(sender, "sent", 0)), ACCENT),
               ("DESCARTES", str(getattr(sender, "dropped", 0)), WHEEL_LEFT),
               ("LATENCIA", "12", TEXT_PRIMARY)]
    mw = (w - 36) // 3
    for i, (label, val, col) in enumerate(metrics):
        mx = x + 18 + i * mw
        _text(canvas, label, mx, my, 0.3, TEXT_MUTED, 1)
        _text(canvas, val, mx, my + 22, 0.7, col, 1)
        if label == "LATENCIA":
            _text(canvas, "ms", mx + 30, my + 22, 0.35, TEXT_MUTED, 1)
    return card_h


def _wheels_card(canvas, x, y, w, poses, settings, last_payload):
    card_h = 300
    _round_rect(canvas, x, y, w, card_h, 12, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + card_h), BORDER, 1)
    # header
    _text(canvas, "RUEDAS", x + 18, y + 24, 0.35, TEXT_MUTED, 1)
    _text(canvas, "DIFERENCIAL", x + w - 18, y + 24, 0.3, TEXT_MUTED, 1, align="right")
    cy = y + 40
    bar_w = w - 36
    for side, color in (("L", WHEEL_LEFT), ("R", WHEEL_RIGHT)):
        pose = poses.get(side)
        speed = pose.speed(settings.max_speed) if pose else 0.0
        idx = pose.index_ext * 100 if pose else 0.0
        med = pose.middle_ext * 100 if pose else 0.0
        # top row
        _text(canvas, f"MOTOR {'IZQUIERDO' if side == 'L' else 'DERECHO'}",
              x + 18, cy + 14, 0.35, TEXT_SECONDARY, 1)
        _text(canvas, side, x + w - 30, cy + 12, 0.3, TEXT_MUTED, 1)
        _text(canvas, f"{speed:+.0f}", x + w - 18, cy + 20, 0.9, color, 1, align="right")
        # bar
        by = cy + 30
        bh = 10
        _round_rect(canvas, x + 18, by, bar_w, bh, 999, SEGMENT_OFF, -1)
        center = x + 18 + bar_w // 2
        fraction = _clamp(speed / max(1, settings.max_speed), -1.0, 1.0)
        length = int((bar_w // 2) * abs(fraction))
        if length > 0:
            if fraction >= 0:
                _round_rect(canvas, center, by, length, bh, 999, color, -1)
            else:
                _round_rect(canvas, center - length, by, length, bh, 999, color, -1)
        # center tick
        cv2.line(canvas, (center, by - 2), (center, by + bh + 2), TEXT_MUTED, 1)
        # scale
        sy = by + bh + 12
        _text(canvas, "-255", x + 18, sy, 0.3, TEXT_MUTED, 1)
        _text(canvas, "0", x + 18 + bar_w // 2, sy, 0.3, TEXT_MUTED, 1, align="center")
        _text(canvas, "+255", x + 18 + bar_w, sy, 0.3, TEXT_MUTED, 1, align="right")
        # foot
        fy = sy + 12
        _text(canvas, f"ÍNDICE {idx:3.0f}% · MEDIO {med:3.0f}%", x + 18, fy + 10, 0.35, TEXT_MUTED, 1)
        delta = (idx - med) if pose else 0.0
        _text(canvas, f"Δ {delta:+.0f}", x + w - 18, fy + 10, 0.35, color, 1, align="right")
        cy += 140
        if side == "L":
            cv2.line(canvas, (x + 18, cy - 10), (x + w - 18, cy - 10), BORDER, 1)
    # drive note
    note = "SIN MANOS -> E-STOP" if not poses else ""
    if poses:
        ls = poses.get("L").speed(settings.max_speed) if "L" in poses else 0.0
        rs = poses.get("R").speed(settings.max_speed) if "R" in poses else 0.0
        if ls > 10 and rs > 10:
            note = "AMBAS RUEDAS ADELANTE"
        elif ls < -10 and rs < -10:
            note = "AMBAS RUEDAS ATRÁS"
        elif abs(ls) < 10 and abs(rs) < 10:
            note = "PARADO"
        else:
            note = "GIRO DIFERENCIAL"
    _text(canvas, note, x + w // 2, y + card_h - 12, 0.3, TEXT_MUTED, 1, align="center")
    return card_h


def _command_card(canvas, x, y, w, last_payload, settings):
    card_h = 150
    _round_rect(canvas, x, y, w, card_h, 12, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + card_h), BORDER, 1)
    _text(canvas, "ÚLTIMA ORDEN", x + 18, y + 24, 0.35, TEXT_MUTED, 1)
    _text(canvas, "ASCII · NUS", x + w - 18, y + 24, 0.3, TEXT_MUTED, 1, align="right")
    # packet preview
    px, py, pw, ph = x + 18, y + 38, w - 36, 52
    _round_rect(canvas, px, py, pw, ph, 8, INPUT, -1)
    cv2.rectangle(canvas, (px, py), (px + pw, py + ph), BORDER, 1)
    # TX label + messages
    _text(canvas, "TX", px + 10, py + 20, 0.3, TEXT_MUTED, 1)
    msgs = last_payload.split() if last_payload else []
    mx = px + 40
    for m in msgs[:2]:
        col = WHEEL_LEFT if m.startswith("L") else (WHEEL_RIGHT if m.startswith("R") else TEXT_PRIMARY)
        tw, _ = cv2.getTextSize(m, FONT, 0.5, 1)[0]
        _round_rect(canvas, mx, py + 8, tw + 14, 22, 4, SURFACE_RAISED, -1)
        cv2.rectangle(canvas, (mx, py + 8), (mx + tw + 14, py + 30), BORDER_STRONG, 1)
        _text(canvas, m, mx + 7, py + 24, 0.5, col, 1)
        mx += tw + 20
    _text(canvas, f"{len(msgs)} escrituras", px + pw - 10, py + 20, 0.3, TEXT_MUTED, 1, align="right")
    # stop row
    _round_rect(canvas, px, py + ph + 8, 24, 18, 4, (42, 18, 18), -1)
    cv2.rectangle(canvas, (px, py + ph + 8), (px + 24, py + ph + 26), (90, 38, 38), 1)
    _text(canvas, "z", px + 9, py + ph + 22, 0.4, DANGER, 1)
    _text(canvas, "reserva · parada total", px + 30, py + ph + 22, 0.3, TEXT_MUTED, 1)
    # safety row
    sy = y + card_h - 22
    _text(canvas, "PARADA SEGURA ARMADA", x + 18, sy, 0.3, TEXT_SECONDARY, 1)
    _text(canvas, f"{settings.lost_grace:.2f} s sin manos", x + w - 18, sy, 0.3, TEXT_MUTED, 1, align="right")
    return card_h


def _calibration_card(canvas, x, y, w, settings):
    card_h = 130
    _round_rect(canvas, x, y, w, card_h, 12, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + card_h), BORDER, 1)
    _text(canvas, "CALIBRACIÓN", x + 18, y + 24, 0.35, TEXT_MUTED, 1)
    _text(canvas, "YAML", x + w - 18, y + 24, 0.3, TEXT_MUTED, 1, align="right")
    items = [("CURL LO", f"{settings.curl_lo:.2f}"),
             ("CURL HI", f"{settings.curl_hi:.2f}"),
             ("EMA", f"{settings.smoothing:.2f}"),
             ("DEADZONE", f"{settings.deadzone:.2f}")]
    ix = x + 18
    iw = (w - 36) // 2
    for i, (label, val) in enumerate(items):
        col = x + 18 + (i % 2) * iw
        row = y + 46 + (i // 2) * 40
        _text(canvas, label, col, row, 0.3, TEXT_MUTED, 1)
        _text(canvas, val, col, row + 16, 0.5, ACCENT, 1)
    return card_h


def render(
    frame: np.ndarray,
    poses: dict[str, HandPose],
    sender: ICommandSender | None,
    fps: float,
    settings: Settings,
    last_payload: str,
    screen: str = "live",
    panel=None,
) -> np.ndarray:
    """Devuelve el dashboard completo (1440x900) con la pantalla indicada."""
    canvas = np.full((H, W, 3), BG, dtype=np.uint8)

    # top bar
    active_tab = "EN VIVO"
    if screen == "settings":
        active_tab = "AJUSTES"
    elif screen == "calibration":
        active_tab = "CALIBRACIÓN"
    dry_run = bool(getattr(sender, "is_dry_run", False)) if sender is not None else False
    ble_connected = bool(getattr(sender, "connected", False)) if sender is not None else False
    addr = settings.address if (panel is None) else (panel.state.ble_address)
    _top_bar(canvas, active_tab, ble_connected, dry_run, addr)

    # layout regions
    body_y = TOP_H
    inner_y = body_y + PAD
    inner_h = H - body_y - PAD * 2  # not exactly but ok
    # left column
    left_x = PAD
    left_w = W - PAD * 2 - 20 - SIDE_W
    # camera stage
    stage_x = left_x
    stage_y = inner_y
    stage_w = left_w
    stage_h = 694
    _camera_stage(canvas, frame, poses, fps, settings, stage_x, stage_y, stage_w, stage_h)

    if screen == "live":
        # legend bar
        legend_y = stage_y + stage_h + 14
        legend_h = 64
        _legend_bar(canvas, stage_x, legend_y, stage_w, legend_h)
    else:
        # telemetry bar (settings screen)
        tel_y = stage_y + stage_h + 14
        tel_h = 64
        _telemetry_bar(canvas, stage_x, tel_y, stage_w, poses, settings)

    # right sidebar
    side_x = left_x + left_w + 20
    side_y = inner_y
    side_h = inner_h
    if screen == "live":
        _sidebar_live(canvas, side_x, side_y, SIDE_W, side_h, sender, settings, poses, last_payload)
    else:
        _sidebar_settings(canvas, side_x, side_y, SIDE_W, side_h, settings, panel)

    return canvas


def _telemetry_bar(canvas, x, y, w, poses, settings):
    _round_rect(canvas, x, y, w, 64, 10, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + 64), BORDER, 1)
    # title
    _text(canvas, "TELEMETRÍA", x + 18, y + 22, 0.35, TEXT_MUTED, 1)
    _text(canvas, "RUEDAS L / R", x + 18, y + 36, 0.3, TEXT_MUTED, 1)
    # wheels
    wx = x + 160
    ww = (w - 180) // 2
    for side, color in (("L", WHEEL_LEFT), ("R", WHEEL_RIGHT)):
        pose = poses.get(side)
        speed = pose.speed(settings.max_speed) if pose else 0.0
        idx = pose.index_ext * 100 if pose else 0.0
        med = pose.middle_ext * 100 if pose else 0.0
        _text(canvas, f"RUEDA {side}", wx, y + 16, 0.35, color, 1)
        _text(canvas, f"{speed:+.0f}", wx + ww - 10, y + 26, 0.7, TEXT_PRIMARY, 1, align="right")
        # segments
        sy = y + 34
        sh = 8
        segs = 12
        seg_w = (ww - 4) // segs
        filled = int(round(abs(speed) / max(1, settings.max_speed) * segs))
        for i in range(segs):
            sx = wx + i * (seg_w + 2)
            col = color if i < filled else SEGMENT_OFF
            _round_rect(canvas, sx, sy, seg_w, sh, 2, col, -1)
        _text(canvas, f"ADELANTE · idx {idx:3.0f}% · med {med:3.0f}%",
              wx, y + 56, 0.3, TEXT_MUTED, 1)
        wx += ww + 10


def _sidebar_live(canvas, x, y, w, h, sender, settings, poses, last_payload):
    cy = y
    ch = _ble_card(canvas, x, cy, w, sender, settings, poses)
    cy += ch + 14
    ch = _wheels_card(canvas, x, cy, w, poses, settings, last_payload)
    cy += ch + 14
    ch = _command_card(canvas, x, cy, w, last_payload, settings)
    cy += ch + 14
    if cy + 130 <= y + h:
        _calibration_card(canvas, x, cy, w, settings)


def _sidebar_settings(canvas, x, y, w, h, settings, panel):
    # config card
    card_h = h
    _round_rect(canvas, x, y, w, card_h, 12, SURFACE, -1)
    cv2.rectangle(canvas, (x, y), (x + w, y + card_h), BORDER, 1)
    # header
    _text(canvas, "Configuración", x + 16, y + 30, 0.65, TEXT_PRIMARY, 1)
    _text(canvas, "Panel de control · cambios en caliente", x + 16, y + 46, 0.4, TEXT_SECONDARY, 1)
    # yaml badge
    _round_rect(canvas, x + w - 60, y + 16, 44, 18, 999, ACCENT_DIM, -1)
    _text(canvas, "YAML", x + w - 48, y + 29, 0.3, ACCENT, 1)
    # intro
    _text(canvas, "Edita los valores y pulsa Guardar.", x + 16, y + 68, 0.4, TEXT_MUTED, 1)
    # divider
    cv2.line(canvas, (x + 16, y + 78), (x + w - 16, y + 78), BORDER, 1)
    # section: calibration
    _text(canvas, "CALIBRACIÓN GESTUAL", x + 16, y + 96, 0.35, TEXT_SECONDARY, 1)
    _text(canvas, "gestures.yaml", x + w - 16, y + 96, 0.3, TEXT_MUTED, 1, align="right")
    # fields
    fy = y + 108
    state = panel.state if panel is not None else None
    curl_lo = state.curl_lo if state else settings.curl_lo
    curl_hi = state.curl_hi if state else settings.curl_hi
    # curl_lo
    _text(canvas, "curl_lo", x + 16, fy, 0.3, TEXT_MUTED, 1)
    _round_rect(canvas, x + 16, fy + 6, w - 32, 30, 8, INPUT, -1)
    cv2.rectangle(canvas, (x + 16, fy + 6), (x + w - 16, fy + 36), BORDER, 1)
    _text(canvas, f"{curl_lo:.2f}", x + 28, fy + 26, 0.45, TEXT_PRIMARY, 1)
    _text(canvas, "0–1", x + w - 28, fy + 26, 0.3, TEXT_MUTED, 1, align="right")
    fy += 46
    _text(canvas, "curl_hi", x + 16, fy, 0.3, TEXT_MUTED, 1)
    _round_rect(canvas, x + 16, fy + 6, w - 32, 30, 8, INPUT, -1)
    cv2.rectangle(canvas, (x + 16, fy + 6), (x + w - 16, fy + 36), BORDER, 1)
    _text(canvas, f"{curl_hi:.2f}", x + 28, fy + 26, 0.45, TEXT_PRIMARY, 1)
    _text(canvas, "0–1", x + w - 28, fy + 26, 0.3, TEXT_MUTED, 1, align="right")
    fy += 46
    _text(canvas, "Rectitud que mapea a 0 % y 100 % de extensión.", x + 16, fy, 0.35, TEXT_MUTED, 1)
    fy += 16
    cv2.line(canvas, (x + 16, fy), (x + w - 16, fy), BORDER, 1)
    fy += 14
    # control mode
    _text(canvas, "MODO DE CONTROL", x + 16, fy, 0.35, TEXT_SECONDARY, 1)
    _text(canvas, "control_mode", x + w - 16, fy, 0.3, TEXT_MUTED, 1, align="right")
    fy += 14
    mode = state.control_mode if state else settings.single_hand
    _round_rect(canvas, x + 16, fy, w - 32, 30, 8, INPUT, -1)
    cv2.rectangle(canvas, (x + 16, fy), (x + w - 16, fy + 30), BORDER, 1)
    # own
    own_fill = ACCENT_DIM if mode == "own" else (0, 0, 0)
    _round_rect(canvas, x + 19, fy + 3, (w - 38) // 2, 24, 6, own_fill, -1)
    _text(canvas, "OWN", x + 19 + (w - 38) // 4, fy + 19, 0.35,
          ACCENT if mode == "own" else TEXT_MUTED, 1, align="center")
    both_fill = ACCENT_DIM if mode == "both" else (0, 0, 0)
    _round_rect(canvas, x + 19 + (w - 38) // 2 + 3, fy + 3, (w - 38) // 2, 24, 6, both_fill, -1)
    _text(canvas, "BOTH", x + 19 + (w - 38) // 2 + 3 + (w - 38) // 4, fy + 19, 0.35,
          ACCENT if mode == "both" else TEXT_MUTED, 1, align="center")
    fy += 36
    _text(canvas, "own: cada mano mueve su rueda · both: una mano mueve las dos.",
          x + 16, fy, 0.35, TEXT_MUTED, 1)
    fy += 16
    cv2.line(canvas, (x + 16, fy), (x + w - 16, fy), BORDER, 1)
    fy += 14
    # ble
    _text(canvas, "BLUETOOTH", x + 16, fy, 0.35, TEXT_SECONDARY, 1)
    _text(canvas, "settings.yaml", x + w - 16, fy, 0.3, TEXT_MUTED, 1, align="right")
    fy += 14
    # device name
    _text(canvas, "DISPOSITIVO BLE", x + 16, fy, 0.3, TEXT_MUTED, 1)
    fy += 6
    ble_name = (state.ble_name if state else settings.name) or ""
    _round_rect(canvas, x + 16, fy, w - 32, 30, 8, INPUT, -1)
    cv2.rectangle(canvas, (x + 16, fy), (x + w - 16, fy + 30), BORDER, 1)
    _text(canvas, ble_name or "BBC micro:bit", x + 28, fy + 20, 0.4, TEXT_PRIMARY, 1)
    _text(canvas, "device_name", x + w - 28, fy + 20, 0.3, TEXT_MUTED, 1, align="right")
    fy += 40
    _text(canvas, "DIRECCIÓN MAC", x + 16, fy, 0.3, TEXT_MUTED, 1)
    fy += 6
    ble_addr = state.ble_address if state else settings.address
    _round_rect(canvas, x + 16, fy, w - 32, 30, 8, INPUT, -1)
    cv2.rectangle(canvas, (x + 16, fy), (x + w - 16, fy + 30), BORDER, 1)
    _text(canvas, ble_addr, x + 28, fy + 20, 0.4, TEXT_PRIMARY, 1)
    _text(canvas, "address", x + w - 28, fy + 20, 0.3, TEXT_MUTED, 1, align="right")
    fy += 40
    _text(canvas, "El nombre tiene prioridad; déjalo vacío para usar la MAC.",
          x + 16, fy, 0.35, TEXT_MUTED, 1)
    fy += 16
    cv2.line(canvas, (x + 16, fy), (x + w - 16, fy), BORDER, 1)
    fy += 14
    # mirror toggle
    _text(canvas, "mirror", x + 16, fy + 4, 0.35, TEXT_SECONDARY, 1)
    _text(canvas, "Espejo de cámara · voltea antes de inferir", x + 16, fy + 20, 0.35, TEXT_MUTED, 1)
    mirror = state.mirror if state else settings.mirror
    _text(canvas, "ON" if mirror else "OFF", x + w - 60, fy + 4, 0.3, ACCENT if mirror else TEXT_MUTED, 1)
    _round_rect(canvas, x + w - 46, fy, 42, 20, 999, ACCENT_DIM if mirror else SEGMENT_OFF, -1)
    knob_x = x + w - 26 if mirror else x + w - 42
    cv2.circle(canvas, (knob_x, fy + 10), 7, ACCENT if mirror else TEXT_MUTED, -1, cv2.LINE_AA)
    fy += 36
    # spacer + footer
    footer_y = y + card_h - 90
    cv2.line(canvas, (x + 16, footer_y), (x + w - 16, footer_y), BORDER, 1)
    # status
    dirty = panel.dirty if panel is not None else False
    status_text = "CAMBIOS SIN GUARDAR" if dirty else "SINCRONIZADO CON YAML"
    dot_col = WHEEL_LEFT if dirty else ACCENT
    cv2.circle(canvas, (x + 22, footer_y + 14), 3, dot_col, -1, cv2.LINE_AA)
    _text(canvas, status_text, x + 32, footer_y + 18, 0.3, TEXT_MUTED, 1)
    _text(canvas, "v2", x + w - 16, footer_y + 18, 0.3, TEXT_MUTED, 1, align="right")
    # save button
    btn_y = footer_y + 26
    _round_rect(canvas, x + 16, btn_y, w - 32, 36, 8, ACCENT, -1)
    _text(canvas, "Guardar Configuración", x + w // 2, btn_y + 23, 0.45, ON_ACCENT, 1, align="center")
    _text(canvas, "Los cambios se aplican al instante. Si cambia la MAC, BLE se reconecta.",
          x + 16, btn_y + 52, 0.3, TEXT_MUTED, 1)

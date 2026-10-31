# -*- coding: utf-8 -*-
"""Cargador del diseño pen.dev (design/car_control_ui.layout.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pc_app.config import BASE_DIR

DEFAULT_LAYOUT_PATH = BASE_DIR / "design" / "car_control_ui.layout.json"

# Paleta institucional Universidad del Tolima (rojo principal).
TOLIMA_PALETTE = {
    "bg": "#F2F2F2",
    "surface": "#FFFFFF",
    "surface-raised": "#F0F0F0",
    "border": "#D0D0D0",
    "border-strong": "#B0B0B0",
    "text-primary": "#1A1A1A",
    "text-secondary": "#444444",
    "text-muted": "#777777",
    "accent": "#FF1744",
    "accent-dim": "#FFCDD2",
    "wheel-left": "#FFD600",
    "wheel-right": "#FF1744",
    "danger": "#D32F2F",
    "input": "#FFFFFF",
    "on-accent": "#FFFFFF",
    "segment-off": "#E0E0E0",
}



def _hex_to_bgr(value: str) -> tuple[int, int, int]:
    text = str(value).strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 8:
        text = text[:6]
    if len(text) != 6:
        return (0, 0, 0)
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return (b, g, r)


@dataclass
class PenTheme:
    mode: str
    colors: dict[str, tuple[int, int, int]]
    fonts: dict[str, str]
    window_width: int
    window_height: int
    top_bar_height: int
    sidebar_width: int

    def color(self, name: str, fallback: tuple[int, int, int] = (0, 0, 0)) -> tuple[int, int, int]:
        return self.colors.get(name, fallback)


@dataclass
class PenLayout:
    theme: PenTheme
    live: dict[str, Any]
    settings: dict[str, Any]
    calibration: dict[str, Any]


def _resolve_color(value: Any, color_map: dict[str, str]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        key = value[1:]
        return color_map.get(key, value)
    if isinstance(value, dict):
        return {k: _resolve_color(v, color_map) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_color(v, color_map) for v in value]
    return value


class PenUiLoader:
    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path is not None else DEFAULT_LAYOUT_PATH
        self._raw: dict[str, Any] = {}
        if self._path.exists():
            try:
                self._raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._raw = {}

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    def load(self) -> PenLayout:
        theme_raw = self._raw.get("theme", {}) or {}
        mode = theme_raw.get("mode", "dark")
        window = theme_raw.get("window", {}) or {}
        colors_raw = theme_raw.get("colors", {}) or {}
        # Aplicamos la paleta institucional de la Universidad del Tolima (rojo).
        colors_raw = {**colors_raw, **TOLIMA_PALETTE}
        color_map = {k: v for k, v in colors_raw.items()}
        colors_bgr = {k: _hex_to_bgr(v) for k, v in colors_raw.items()}
        fonts = theme_raw.get("fonts", {}) or {}

        theme = PenTheme(
            mode=mode,
            colors=colors_bgr,
            fonts=fonts,
            window_width=int(window.get("width", 1440)),
            window_height=int(window.get("height", 900)),
            top_bar_height=int(window.get("top_bar_height", 64)),
            sidebar_width=int(window.get("sidebar_width", 380)),
        )

        live = self._raw.get("live", {}) or {}
        settings = self._raw.get("settings", {}) or {}
        calibration = self._raw.get("calibration", {}) or {}

        live = _resolve_color(live, color_map)
        settings = _resolve_color(settings, color_map)

        return PenLayout(theme=theme, live=live, settings=settings, calibration=calibration)


def load_design(path: Path | None = None) -> PenLayout:
    return PenUiLoader(path).load()


_DEFAULT_LAYOUT: PenLayout | None = None


def get_design() -> PenLayout:
    global _DEFAULT_LAYOUT
    if _DEFAULT_LAYOUT is None:
        _DEFAULT_LAYOUT = load_design()
    return _DEFAULT_LAYOUT

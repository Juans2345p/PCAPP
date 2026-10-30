# -*- coding: utf-8 -*-
"""Descarga/verificación del modelo `hand_landmarker.task`."""

from __future__ import annotations

import logging
import shutil
import urllib.request
from pathlib import Path

LOG = logging.getLogger("gesture-cart.model")

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)


def ensure_model(path: Path) -> None:
    """Descarga el modelo si no está disponible o está incompleto."""
    if path.exists() and path.stat().st_size > 1_000_000:
        return
    LOG.info("Descargando modelo en %s ...", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response, open(tmp, "wb") as fh:
            shutil.copyfileobj(response, fh)
        tmp.replace(path)
    except Exception as exc:  # noqa: BLE001 - se informa y se aborta
        tmp.unlink(missing_ok=True)
        raise SystemExit(
            f"No se pudo descargar el modelo ({exc}).\n"
            f"Descárgalo manualmente en: {MODEL_URL}\n"
            f"y guárdalo como: {path.resolve()}"
        ) from exc
    LOG.info("Modelo listo (%.1f MB)", path.stat().st_size / 1e6)

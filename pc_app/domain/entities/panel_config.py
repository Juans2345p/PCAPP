# -*- coding: utf-8 -*-
"""Valores editables desde el panel de Configuración de la UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelConfig:
    """Valores editables que controla la pantalla de Configuración."""

    curl_lo: float
    curl_hi: float
    control_mode: str
    ble_address: str
    ble_name: str | None
    mirror: bool
    deadzone: float = 0.08
    smoothing: float = 0.35
    step: int = 5
    lost_grace: float = 0.15
    speed_multiplier: float = 1.0

    def validate(self) -> None:
        if not 0.0 <= self.curl_lo < self.curl_hi:
            raise ValueError("curl_hi debe ser mayor que curl_lo (ambos >= 0)")
        if self.control_mode not in ("own", "both"):
            raise ValueError("El modo de control debe ser 'own' o 'both'")
        if not self.ble_address.strip():
            raise ValueError("La dirección MAC no puede estar vacía")
        if not 0.0 <= self.deadzone < 1.0:
            raise ValueError("La zona STOP debe estar en el rango [0, 1)")
        if not 0.0 < self.smoothing <= 1.0:
            raise ValueError("El suavizado debe estar en el rango (0, 1]")
        if self.step < 1:
            raise ValueError("El paso debe ser >= 1")
        if self.lost_grace < 0.0:
            raise ValueError("La pérdida debe ser >= 0")
        if not 0.0 <= self.speed_multiplier <= 1.5:
            raise ValueError("El multiplicador debe estar en el rango 0.0–1.5")

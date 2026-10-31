# -*- coding: utf-8 -*-
"""Valores editables desde el panel de Configuración de la UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelConfig:
    """Borrador de los campos que controla la pantalla de Configuración."""

    curl_lo: float
    curl_hi: float
    control_mode: str
    ble_address: str
    ble_name: str | None
    mirror: bool

    def validate(self) -> None:
        if not 0.0 <= self.curl_lo < self.curl_hi:
            raise ValueError("curl_hi debe ser mayor que curl_lo (ambos >= 0)")
        if self.control_mode not in ("own", "both"):
            raise ValueError("El modo de control debe ser 'own' o 'both'")
        if not self.ble_address.strip():
            raise ValueError("La dirección MAC no puede estar vacía")

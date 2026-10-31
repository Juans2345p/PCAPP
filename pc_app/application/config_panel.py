# -*- coding: utf-8 -*-
"""Eventos del panel de Configuración: borrador, guardado y aplicación."""

from __future__ import annotations

import logging
from dataclasses import replace

from pc_app.config import Settings
from pc_app.domain.entities.panel_config import PanelConfig
from pc_app.domain.interfaces.config_store import IConfigStore

LOG = logging.getLogger("gesture-cart.config-panel")


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "sí", "si"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"Valor booleano inválido: {value!r}")


class ConfigurationPanelController:
    """Traduce los eventos de la UI a cambios persistentes en los YAML.

    Flujo típico de la pantalla:
    1. ``ConfigurationPanelController(store, settings)`` lee el estado actual.
    2. Cada control llama a su ``set_*`` y persiste el valor validado al instante.
    """

    def __init__(
        self,
        store: IConfigStore,
        settings: Settings | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._state = store.read_panel()
        self._dirty = False
        if settings is not None:
            candidate = self._candidate_settings()
            candidate.validate()
            self._apply(candidate)

    # -- estado --------------------------------------------------------------
    @property
    def state(self) -> PanelConfig:
        return self._state

    @property
    def dirty(self) -> bool:
        return self._dirty

    def reload(self) -> PanelConfig:
        """Relee los YAML (por si se editaron fuera de la UI)."""
        self._state = self._store.read_panel()
        if self._settings is not None:
            candidate = self._candidate_settings()
            candidate.validate()
            self._apply(candidate)
        self._dirty = False
        return self._state

    # -- eventos de los controles -------------------------------------------
    def _update(self, **changes: object) -> PanelConfig:
        previous = self._state
        self._state = replace(previous, **changes)
        if self._settings is not None:
            try:
                candidate = self._candidate_settings()
                candidate.validate()
            except Exception:
                self._state = previous
                raise
            self._apply(candidate)
        self._dirty = True
        self.save()
        return self._state

    def set_curl_lo(self, value: float | str) -> PanelConfig:
        return self._update(curl_lo=float(value))

    def set_curl_hi(self, value: float | str) -> PanelConfig:
        return self._update(curl_hi=float(value))

    def set_control_mode(self, value: str) -> PanelConfig:
        mode = str(value).strip().lower()
        if mode not in ("own", "both"):
            raise ValueError("El modo de control debe ser 'own' o 'both'")
        return self._update(control_mode=mode)

    def set_ble_address(self, value: str) -> PanelConfig:
        return self._update(ble_address=str(value).strip())

    def set_ble_name(self, value: str | None) -> PanelConfig:
        text = "" if value is None else str(value).strip()
        return self._update(ble_name=text or None)

    def set_mirror(self, value: object) -> PanelConfig:
        return self._update(mirror=_coerce_bool(value))

    def set_deadzone(self, value: float | str) -> PanelConfig:
        return self._update(deadzone=float(value))

    def set_smoothing(self, value: float | str) -> PanelConfig:
        return self._update(smoothing=float(value))

    def set_step(self, value: int | str) -> PanelConfig:
        return self._update(step=int(value))

    def set_lost_grace(self, value: float | str) -> PanelConfig:
        return self._update(lost_grace=float(value))

    def set_speed_multiplier(self, value: float | str) -> PanelConfig:
        return self._update(speed_multiplier=float(value))

    # -- guardado ------------------------------------------------------------
    def _candidate_settings(self) -> Settings:
        assert self._settings is not None
        return replace(
            self._settings,
            curl_lo=self._state.curl_lo,
            curl_hi=self._state.curl_hi,
            single_hand=self._state.control_mode,
            address=self._state.ble_address,
            name=self._state.ble_name,
            mirror=self._state.mirror,
            deadzone=self._state.deadzone,
            smoothing=self._state.smoothing,
            step=self._state.step,
            lost_grace=self._state.lost_grace,
            speed_multiplier=self._state.speed_multiplier,
        )

    def _apply(self, candidate: Settings) -> None:
        assert self._settings is not None
        self._settings.curl_lo = candidate.curl_lo
        self._settings.curl_hi = candidate.curl_hi
        self._settings.single_hand = candidate.single_hand
        self._settings.address = candidate.address
        self._settings.name = candidate.name
        self._settings.mirror = candidate.mirror
        self._settings.deadzone = candidate.deadzone
        self._settings.smoothing = candidate.smoothing
        self._settings.step = candidate.step
        self._settings.lost_grace = candidate.lost_grace
        self._settings.speed_multiplier = candidate.speed_multiplier

    def save(self) -> PanelConfig:
        """Valida y persiste el estado actual en los YAML."""
        self._state.validate()
        candidate = self._candidate_settings() if self._settings is not None else None
        if candidate is not None:
            candidate.validate()
        self._store.write_panel(self._state)
        if candidate is not None:
            self._apply(candidate)
        self._dirty = False
        LOG.info(
            "Configuración guardada: stop=%.2f multiplicador=%.2f modo=%s mirror=%s BLE=%s",
            self._state.deadzone,
            self._state.speed_multiplier,
            self._state.control_mode,
            "sí" if self._state.mirror else "no",
            self._state.ble_name or self._state.ble_address,
        )
        return self._state

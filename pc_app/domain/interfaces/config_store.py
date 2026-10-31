# -*- coding: utf-8 -*-
"""Contrato de persistencia del panel de Configuración."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pc_app.domain.entities.panel_config import PanelConfig


class IConfigStore(ABC):
    """Lee y escribe los valores editables en la configuración persistente."""

    @abstractmethod
    def read_panel(self) -> PanelConfig:
        """Devuelve el estado actual leído de los YAML."""

    @abstractmethod
    def write_panel(self, config: PanelConfig) -> None:
        """Persiste el estado validado en los YAML."""

# -*- coding: utf-8 -*-
"""Envío de órdenes al carrito: BLE real, dry-run o un mock de pruebas."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ICommandSender(ABC):
    """Transporte de los mensajes ASCII del protocolo del micro:bit."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """``True`` si el enlace está listo para escribir."""

    @property
    @abstractmethod
    def sent(self) -> int:
        """Número de órdenes enviadas correctamente."""

    @property
    @abstractmethod
    def dropped(self) -> int:
        """Órdenes descartadas por la cola de tamaño 1."""

    @property
    @abstractmethod
    def last_error(self) -> str | None:
        """Último error de conexión/escritura, si lo hubo."""

    @property
    def is_dry_run(self) -> bool:
        return False

    @abstractmethod
    def start(self) -> None:
        """Arranca el transporte (conexión, supervisor, etc.)."""

    @abstractmethod
    def send(self, messages: tuple[str, ...]) -> None:
        """Encola una orden; no debe bloquear el bucle de visión."""

    @abstractmethod
    async def close(self, final: str | None = "z") -> None:
        """Cierra el transporte enviando, si procede, la parada de seguridad."""

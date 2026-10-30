# -*- coding: utf-8 -*-
"""Transporte de pruebas: registra las órdenes sin tocar Bluetooth."""

from __future__ import annotations

import logging

from pc_app.domain.interfaces.command_sender import ICommandSender

LOG = logging.getLogger("gesture-cart.dry-run")


class DryRunCommandSender(ICommandSender):
    """Implementación sin hardware para ``--dry-run``."""

    def __init__(self) -> None:
        self._sent = 0

    @property
    def connected(self) -> bool:
        return False

    @property
    def sent(self) -> int:
        return self._sent

    @property
    def dropped(self) -> int:
        return 0

    @property
    def last_error(self) -> str | None:
        return None

    @property
    def is_dry_run(self) -> bool:
        return True

    def start(self) -> None:
        LOG.info("Modo dry-run: no se enviará nada por BLE")

    def send(self, messages: tuple[str, ...]) -> None:
        self._sent += 1
        LOG.debug("dry-run -> %s", " ".join(messages))

    async def close(self, final: str | None = "z") -> None:
        if final:
            self._sent += 1
            LOG.debug("dry-run close -> %s", final)

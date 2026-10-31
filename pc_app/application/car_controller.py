# -*- coding: utf-8 -*-
"""Orquestación: manos detectadas -> velocidad por rueda -> enlace BLE."""

from __future__ import annotations

import logging
import time

from pc_app.application.command_gate import CommandGate
from pc_app.config import Settings
from pc_app.domain.entities.hand_pose import HandPose
from pc_app.domain.entities.wheel_command import WheelCommand
from pc_app.domain.interfaces.command_sender import ICommandSender

LOG = logging.getLogger("gesture-cart.controller")

SIDES = ("L", "R")


class CarController:
    """Coordina reconocedor, puerta de comandos y transporte.

    Mantiene la última pose y el instante en que se vio cada mano para poder
    aplicar la gracia de pérdida por rueda. No conoce OpenCV ni bleak: sólo
    habla con las interfaces del dominio.
    """

    def __init__(
        self,
        settings: Settings,
        sender: ICommandSender,
        gate: CommandGate | None = None,
    ) -> None:
        self._settings = settings
        self._sender = sender
        self._gate = gate or CommandGate(settings)
        self._last_pose: dict[str, HandPose] = {}
        self._last_seen: dict[str, float] = {}
        self.last_command = WheelCommand.stop()
        self.last_payload = "-"
        self.enabled = True

    # -- propiedades para la interfaz ---------------------------------------
    @property
    def sender(self) -> ICommandSender:
        return self._sender

    @property
    def gate(self) -> CommandGate:
        return self._gate

    # -- ciclo de vida -------------------------------------------------------
    def start(self) -> None:
        """Arranca el transporte y envía la parada inicial de seguridad."""
        self._sender.start()
        stop = WheelCommand.stop()
        self._sender.send(stop.messages())
        self.last_command = stop
        LOG.info("Parada de seguridad inicial enviada (z)")

    async def stop(self) -> None:
        """Cierra el transporte enviando siempre la parada final."""
        await self._sender.close("z")

    # -- control -------------------------------------------------------------
    def update(
        self,
        poses: dict[str, HandPose],
        now: float | None = None,
    ) -> WheelCommand | None:
        """Actualiza el estado con las manos del frame y envía si procede."""
        cfg = self._settings
        now = time.monotonic() if now is None else now

        if not self.enabled:
            return None

        for side, pose in poses.items():
            if side in SIDES:
                self._last_pose[side] = pose
                self._last_seen[side] = now

        # Cada rueda usa su mano; si falta o lleva más de `lost_grace` sin
        # verse, su velocidad es 0. Sin ninguna mano -> 'z' (e-stop).
        speeds = {
            side: self._last_pose[side].speed(
                cfg.max_speed, cfg.deadzone, cfg.speed_multiplier
            )
            for side in SIDES
            if side in self._last_pose
            and now - self._last_seen[side] <= cfg.lost_grace
        }
        if cfg.single_hand == "both" and len(speeds) == 1:
            only = next(iter(speeds.values()))
            speeds = {"L": only, "R": only}

        command = self._gate.feed(speeds, now)
        if command is not None:
            self.last_command = command
            self.last_payload = self._gate.last_payload
            LOG.info("orden -> %s", self.last_payload)
            self._sender.send(command.messages())
        return command

    def toggle_hands(self) -> bool:
        """Invierte izquierda/derecha en caliente (tecla ``h``)."""
        self._settings.swap_hands = not self._settings.swap_hands
        LOG.info(
            "Etiquetas de mano invertidas: %s",
            "SÍ" if self._settings.swap_hands else "NO",
        )
        return self._settings.swap_hands

    def set_enabled(self, enabled: bool) -> bool:
        """Pausa o reanuda el seguimiento; pausar envía una parada inmediata."""
        enabled = bool(enabled)
        if enabled == self.enabled:
            return self.enabled
        self.enabled = enabled
        self._last_pose.clear()
        self._last_seen.clear()
        if not enabled:
            self._gate.feed({}, time.monotonic())
            stop = WheelCommand.stop()
            self._sender.send(stop.messages())
            self.last_command = stop
            self.last_payload = self._gate.last_payload
        LOG.info("Control %s", "activado" if enabled else "pausado")
        return self.enabled

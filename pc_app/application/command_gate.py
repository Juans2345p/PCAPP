# -*- coding: utf-8 -*-
"""Decide *cuándo* se debe enviar una orden por BLE."""

from __future__ import annotations

from pc_app.config import Settings
from pc_app.domain.entities.wheel_command import WheelCommand


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


class CommandGate:
    """Filtra el ruido del tracking y evita saturar el enlace BLE.

    Aplica cuantización (múltiplos de ``step``), histéresis sobre la
    velocidad continua, separación mínima entre envíos y keep-alive. Cada
    rueda se evalúa por separado para que una pueda actualizarse sin la otra.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mode = "init"        # init | drive | stop
        self._left = 0.0           # última velocidad continua enviada
        self._right = 0.0
        self._sent_at = -1e9
        self.last_command = WheelCommand.stop()
        self.last_payload = "-"

    def _emit(self, command: WheelCommand, left: float, right: float,
              now: float, mode: str) -> WheelCommand:
        self._mode = mode
        self._left, self._right = left, right
        self._sent_at = now
        self.last_command = command
        self.last_payload = str(command)
        return command

    def feed(self, speeds: dict[str, float] | None, now: float) -> WheelCommand | None:
        """Devuelve la orden a enviar, o ``None`` si no procede enviar nada.

        ``speeds`` es ``{"L": velocidad, "R": velocidad}``; vacío o ``None``
        equivale a parada de emergencia. La histéresis se evalúa sobre la
        velocidad continua (no la cuantizada) para no parpadear en los
        múltiplos de ``step``.
        """
        cfg = self._settings
        speeds = speeds or {}
        right = _clamp(float(speeds.get("R", 0.0)), -cfg.max_speed, cfg.max_speed)
        left = _clamp(float(speeds.get("L", 0.0)), -cfg.max_speed, cfg.max_speed)
        command = WheelCommand.from_speeds(
            left, right, step=cfg.step, max_speed=cfg.max_speed
        )

        if command.is_stop:  # puños, zona muerta o e-stop
            if self._mode != "stop" or now - self._sent_at >= cfg.heartbeat:
                return self._emit(command, 0.0, 0.0, now, "stop")
            return None

        if self._mode != "drive":
            return self._emit(command, left, right, now, "drive")

        step = max(1, cfg.step)
        changed = abs(right - self._right) >= step or abs(left - self._left) >= step
        if changed and now - self._sent_at >= cfg.min_interval:
            return self._emit(command, left, right, now, "drive")
        if now - self._sent_at >= cfg.heartbeat:
            return self._emit(command, left, right, now, "drive")
        return None

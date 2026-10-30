# -*- coding: utf-8 -*-
"""Orden de movimiento para las dos ruedas y su protocolo ASCII."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WheelCommand:
    """Velocidad ya cuantizada de cada rueda, en unidades del motor.

    El firmware del micro:bit no acepta dos motores en la misma línea: cada
    rueda viaja en un mensaje independiente. Por eso ``messages()`` devuelve
    una tupla que el transporte BLE escribe en escrituras separadas.
    """

    left: int
    right: int

    @classmethod
    def from_speeds(
        cls,
        left: float,
        right: float,
        *,
        step: int,
        max_speed: int,
    ) -> "WheelCommand":
        """Cuantiza a múltiplos de ``step`` y recorta a ±``max_speed``."""
        step = max(1, step)
        limit = max(1, max_speed)

        def quantize(value: float) -> int:
            quantized = int(round(value / step)) * step
            return int(max(-limit, min(limit, quantized)))

        return cls(left=quantize(left), right=quantize(right))

    @classmethod
    def stop(cls) -> "WheelCommand":
        return cls(left=0, right=0)

    @property
    def is_stop(self) -> bool:
        return self.left == 0 and self.right == 0

    def messages(self) -> tuple[str, ...]:
        """Mensajes ASCII listos para enviar, en orden izquierda/derecha."""
        if self.is_stop:
            return ("z",)
        return (f"L{self.left}", f"R{self.right}")

    def __str__(self) -> str:
        return " ".join(self.messages())

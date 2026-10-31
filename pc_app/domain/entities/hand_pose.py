# -*- coding: utf-8 -*-
"""Resultado del análisis de una mano."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HandPose:
    """Punto de muñeca detectado y su posición vertical suavizada.

    ``index_ext`` y ``middle_ext`` codifican la misma posición normalizada
    como valores complementarios para conservar la interfaz de velocidad.
    """

    side: str                 # "L" (izquierda) | "R" (derecha)
    index_ext: float          # posición vertical mapeada a [0,1]
    middle_ext: float         # complemento de index_ext
    raw_index: float          # posición vertical normalizada [-1,1]
    raw_middle: float         # misma posición, por compatibilidad
    landmarks: list = field(repr=False, default_factory=list)

    def speed(
        self,
        max_speed: int,
        deadzone: float = 0.0,
        multiplier: float = 1.0,
    ) -> float:
        """Calcula velocidad con banda neutra y límite del motor."""
        difference = self.index_ext - self.middle_ext
        magnitude = abs(difference)
        deadzone = max(0.0, min(0.999999, float(deadzone)))
        if magnitude <= deadzone:
            return 0.0
        normalized = (magnitude - deadzone) / (1.0 - deadzone)
        speed = normalized * max_speed * max(0.0, multiplier)
        limit = max(1, min(255, int(max_speed)))
        return (1.0 if difference > 0 else -1.0) * min(limit, speed)

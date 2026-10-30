# -*- coding: utf-8 -*-
"""Resultado del análisis de una mano."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HandPose:
    """Una mano detectada y sus métricas de extensión.

    ``raw_*`` son las rectitudes sin normalizar (útiles para calibrar) y
    ``*_ext`` son los valores ya normalizados, con zona muerta y filtro EMA.
    """

    side: str                 # "L" (izquierda) | "R" (derecha)
    index_ext: float          # extensión suavizada del índice  (0..1)
    middle_ext: float         # extensión suavizada del medio   (0..1)
    raw_index: float          # rectitud cruda del índice (para calibrar)
    raw_middle: float         # rectitud cruda del medio  (para calibrar)
    landmarks: list = field(repr=False, default_factory=list)

    def speed(self, max_speed: int) -> float:
        """Velocidad proporcional de la rueda asociada a esta mano."""
        return (self.index_ext - self.middle_ext) * max_speed

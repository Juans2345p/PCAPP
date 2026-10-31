# -*- coding: utf-8 -*-
"""Dominio del control gestual: entidades y contratos."""

from pc_app.domain.entities import HandPose, PanelConfig, WheelCommand
from pc_app.domain.interfaces import (
    ICommandSender,
    IConfigStore,
    IGestureRecognizer,
)

__all__ = [
    "HandPose",
    "PanelConfig",
    "WheelCommand",
    "ICommandSender",
    "IConfigStore",
    "IGestureRecognizer",
]

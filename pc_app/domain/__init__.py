# -*- coding: utf-8 -*-
"""Dominio del control gestual: entidades y contratos."""

from pc_app.domain.entities import HandPose, WheelCommand
from pc_app.domain.interfaces import ICommandSender, IGestureRecognizer

__all__ = ["HandPose", "WheelCommand", "ICommandSender", "IGestureRecognizer"]

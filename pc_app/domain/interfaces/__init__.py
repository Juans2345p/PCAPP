# -*- coding: utf-8 -*-
"""Contratos del dominio."""

from pc_app.domain.interfaces.command_sender import ICommandSender
from pc_app.domain.interfaces.gesture_recognizer import IGestureRecognizer

__all__ = ["ICommandSender", "IGestureRecognizer"]

# -*- coding: utf-8 -*-
"""Entidades del dominio: no dependen de OpenCV, MediaPipe ni bleak."""

from pc_app.domain.entities.hand_pose import HandPose
from pc_app.domain.entities.panel_config import PanelConfig
from pc_app.domain.entities.wheel_command import WheelCommand

__all__ = ["HandPose", "PanelConfig", "WheelCommand"]

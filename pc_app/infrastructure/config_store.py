# -*- coding: utf-8 -*-
"""Persistencia del panel de Configuración sobre los YAML del proyecto.

La escritura es quirúrgica: sustituye únicamente los escalares gestionados
por la UI y conserva el resto del archivo (incluidos comentarios y orden).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from pc_app.config import (
    DEFAULT_GESTURES_PATH,
    DEFAULT_SETTINGS_PATH,
    Settings,
)
from pc_app.domain.entities.panel_config import PanelConfig
from pc_app.domain.interfaces.config_store import IConfigStore

_KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_.-]+):(.*)$")
_SECTION_RE = re.compile(r"^([A-Za-z0-9_.-]+):\s*(?:#.*)?$")


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "sí", "si"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _split_comment(value: str) -> tuple[str, str]:
    """Separa el valor de un comentario ``#`` que no esté entre comillas."""
    single = double = False
    for index, char in enumerate(value):
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single:
            double = not double
        elif char == "#" and not single and not double:
            return value[:index].rstrip(), value[index:]
    return value.rstrip(), ""


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _set_scalar(text: str, section: str | None, key: str, value: Any) -> str:
    """Sustituye (o añade) ``key`` conservando comentarios y estructura."""
    lines = text.splitlines()
    formatted = _format_scalar(value)

    if section is None:
        for index, line in enumerate(lines):
            match = _KEY_RE.match(line)
            if match and match.group(2) == key and not match.group(1):
                _, comment = _split_comment(match.group(3))
                suffix = f"  {comment}" if comment else ""
                lines[index] = f"{key}: {formatted}{suffix}"
                return "\n".join(lines) + "\n"
        lines.append(f"{key}: {formatted}")
        return "\n".join(lines) + "\n"

    section_index = next(
        (
            index
            for index, line in enumerate(lines)
            if (match := _SECTION_RE.match(line)) and match.group(1) == section
        ),
        None,
    )
    if section_index is None:
        lines.extend([f"{section}:", f"  {key}: {formatted}"])
        return "\n".join(lines) + "\n"

    insert_at = len(lines)
    for index in range(section_index + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            insert_at = index
            break
        match = _KEY_RE.match(line)
        if match and match.group(2) == key:
            _, comment = _split_comment(match.group(3))
            suffix = f"  {comment}" if comment else ""
            lines[index] = f"{match.group(1)}{key}: {formatted}{suffix}"
            return "\n".join(lines) + "\n"

    lines.insert(insert_at, f"  {key}: {formatted}")
    return "\n".join(lines) + "\n"


class YamlConfigStore(IConfigStore):
    """Implementación sobre ``config/settings.yaml`` y ``config/gestures.yaml``."""

    def __init__(
        self,
        settings_path: Path | None = None,
        gestures_path: Path | None = None,
    ) -> None:
        self._settings_path = Path(settings_path or DEFAULT_SETTINGS_PATH)
        self._gestures_path = Path(gestures_path or DEFAULT_GESTURES_PATH)

    # -- lectura -------------------------------------------------------------
    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"No se pudo leer {path}: {exc}") from exc
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(f"{path} debe contener un mapa YAML en la raíz")
        return data

    def read_panel(self) -> PanelConfig:
        base = Settings()
        settings_raw = self._load(self._settings_path)
        gestures_raw = self._load(self._gestures_path)

        camera = settings_raw.get("camera") or {}
        ble = settings_raw.get("ble") or {}
        control = settings_raw.get("control") or {}
        calibration = gestures_raw.get("calibration") or {}

        return PanelConfig(
            curl_lo=float(calibration.get("curl_lo", base.curl_lo)),
            curl_hi=float(calibration.get("curl_hi", base.curl_hi)),
            control_mode=str(
                gestures_raw.get(
                    "control_mode",
                    control.get("single_hand", base.single_hand),
                )
            ).lower(),
            ble_address=str(ble.get("address", base.address)),
            ble_name=_optional_text(
                ble.get("device_name", ble.get("name", base.name))
            ),
            mirror=_as_bool(camera.get("mirror", base.mirror), base.mirror),
            deadzone=float(calibration.get("deadzone", base.deadzone)),
            smoothing=float(calibration.get("smoothing", base.smoothing)),
            step=int(control.get("step", base.step)),
            lost_grace=float(control.get("lost_grace", base.lost_grace)),
            speed_multiplier=float(
                control.get("speed_multiplier", base.speed_multiplier)
            ),
        )

    # -- escritura -----------------------------------------------------------
    def write_panel(self, config: PanelConfig) -> None:
        config.validate()
        settings_text = self._read_text(self._settings_path)
        gestures_text = self._read_text(self._gestures_path)

        settings_text = _set_scalar(settings_text, "ble", "address", config.ble_address)
        settings_text = _set_scalar(settings_text, "ble", "device_name", config.ble_name)
        settings_text = _set_scalar(settings_text, "camera", "mirror", config.mirror)
        settings_text = _set_scalar(
            settings_text, "control", "single_hand", config.control_mode
        )
        settings_text = _set_scalar(settings_text, "control", "step", config.step)
        settings_text = _set_scalar(
            settings_text, "control", "lost_grace", config.lost_grace
        )
        settings_text = _set_scalar(
            settings_text, "control", "speed_multiplier", config.speed_multiplier
        )

        gestures_text = _set_scalar(
            gestures_text, "calibration", "curl_lo", config.curl_lo
        )
        gestures_text = _set_scalar(
            gestures_text, "calibration", "curl_hi", config.curl_hi
        )
        gestures_text = _set_scalar(
            gestures_text, "calibration", "deadzone", config.deadzone
        )
        gestures_text = _set_scalar(
            gestures_text, "calibration", "smoothing", config.smoothing
        )
        gestures_text = _set_scalar(
            gestures_text, None, "control_mode", config.control_mode
        )

        self._write_text(self._settings_path, settings_text)
        self._write_text(self._gestures_path, gestures_text)

    @staticmethod
    def _read_text(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(path)

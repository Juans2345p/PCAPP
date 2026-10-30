# -*- coding: utf-8 -*-
"""Configuración del control gestual.

Los valores por defecto viven en ``config/settings.yaml`` y
``config/gestures.yaml``. La línea de comandos sigue disponible para
sobrescribir cualquier parámetro sin editar los YAML.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

LOG = logging.getLogger("gesture-cart.config")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = BASE_DIR / "config" / "settings.yaml"
DEFAULT_GESTURES_PATH = BASE_DIR / "config" / "gestures.yaml"

UART_WRITE_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # PC -> micro:bit
UART_NOTIFY_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # micro:bit -> PC


@dataclass
class Settings:
    """Todos los parámetros ajustables del sistema."""

    # --- BLE ---
    address: str = "E0:BE:3F:2E:C9:8A"
    name: str | None = None
    write_uuid: str = UART_WRITE_UUID
    notify_uuid: str = UART_NOTIFY_UUID
    reconnect_min: float = 1.0
    reconnect_max: float = 15.0

    # --- Cámara ---
    camera: int = 0
    width: int = 640
    height: int = 480
    mirror: bool = True

    # --- MediaPipe ---
    model: Path = BASE_DIR / "hand_landmarker.task"
    num_hands: int = 2
    detect_conf: float = 0.6
    presence_conf: float = 0.6
    track_conf: float = 0.6

    # --- Mapeo gesto -> velocidad ---
    max_speed: int = 255
    step: int = 8
    min_interval: float = 0.06
    heartbeat: float = 1.0
    lost_grace: float = 0.15
    swap_hands: bool = False
    single_hand: str = "own"

    # --- Calibración de dedos ---
    smoothing: float = 0.35
    deadzone: float = 0.08
    curl_lo: float = 0.30
    curl_hi: float = 0.97

    # --- Varios ---
    preview: bool = True
    dry_run: bool = False
    debug: bool = False
    log_level: str = "INFO"
    list_devices: bool = False
    image: Path | None = None

    def validate(self) -> None:
        if not 1 <= self.max_speed <= 255:
            raise SystemExit("max_speed debe estar entre 1 y 255")
        if self.curl_hi <= self.curl_lo:
            raise SystemExit("curl_hi debe ser mayor que curl_lo")
        if not 0.0 < self.smoothing <= 1.0:
            raise SystemExit("smoothing debe estar en el rango (0, 1]")
        if not 0.0 <= self.deadzone < 1.0:
            raise SystemExit("deadzone debe estar en el rango [0, 1)")
        if self.step < 1:
            raise SystemExit("step debe ser >= 1")
        if self.num_hands < 1:
            raise SystemExit("num_hands debe ser >= 1")
        if self.single_hand not in ("own", "both"):
            raise SystemExit("single_hand debe ser 'own' o 'both'")
        if self.lost_grace < 0 or self.min_interval < 0 or self.heartbeat < 0:
            raise SystemExit("lost_grace, min_interval y heartbeat deben ser >= 0")


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        LOG.warning("No existe %s; se usarán los valores por defecto", path)
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"No se pudo leer {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SystemExit(f"{path} debe contener un mapa YAML en la raíz")
    return data


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SystemExit(f"La sección '{name}' debe ser un mapa YAML")
    return value


def _pick(section: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in section:
            return section[key]
    return default


def _as_path(value: Any, default: Path) -> Path:
    if value is None:
        return default
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


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


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_settings(
    settings_path: Path | None = None,
    gestures_path: Path | None = None,
) -> Settings:
    """Carga los dos YAML y devuelve un `Settings` plano y validado."""
    settings_path = settings_path or DEFAULT_SETTINGS_PATH
    gestures_path = gestures_path or DEFAULT_GESTURES_PATH
    base = Settings()
    raw = _load_yaml(settings_path)
    gestures_raw = _load_yaml(gestures_path)

    camera = _section(raw, "camera")
    mediapipe = _section(raw, "mediapipe")
    ble = _section(raw, "ble")
    control = _section(raw, "control")
    runtime = _section(raw, "runtime")
    calibration = _section(gestures_raw, "calibration")

    settings = Settings(
        # BLE
        address=str(_pick(ble, "address", default=base.address)),
        name=_as_optional_str(_pick(ble, "device_name", "name", default=base.name)),
        write_uuid=str(_pick(ble, "write_uuid", default=base.write_uuid)),
        notify_uuid=str(_pick(ble, "notify_uuid", default=base.notify_uuid)),
        reconnect_min=float(_pick(ble, "reconnect_min", default=base.reconnect_min)),
        reconnect_max=float(_pick(ble, "reconnect_max", default=base.reconnect_max)),
        # Cámara
        camera=int(_pick(camera, "index", "camera", default=base.camera)),
        width=int(_pick(camera, "width", default=base.width)),
        height=int(_pick(camera, "height", default=base.height)),
        mirror=_as_bool(_pick(camera, "mirror", default=base.mirror), base.mirror),
        # MediaPipe
        model=_as_path(_pick(mediapipe, "model_path", "model", default=base.model), base.model),
        num_hands=int(_pick(mediapipe, "num_hands", default=base.num_hands)),
        detect_conf=float(_pick(mediapipe, "detect_conf", default=base.detect_conf)),
        presence_conf=float(_pick(mediapipe, "presence_conf", default=base.presence_conf)),
        track_conf=float(_pick(mediapipe, "track_conf", default=base.track_conf)),
        # Control
        max_speed=int(_pick(control, "max_speed", default=base.max_speed)),
        step=int(_pick(control, "step", default=base.step)),
        min_interval=float(_pick(control, "min_interval", default=base.min_interval)),
        heartbeat=float(_pick(control, "heartbeat", default=base.heartbeat)),
        lost_grace=float(_pick(control, "lost_grace", default=base.lost_grace)),
        swap_hands=_as_bool(
            _pick(control, "swap_hands", default=base.swap_hands), base.swap_hands
        ),
        single_hand=str(
            _pick(
                gestures_raw,
                "single_hand",
                "control_mode",
                default=_pick(control, "single_hand", default=base.single_hand),
            )
        ),
        # Calibración gestual
        smoothing=float(_pick(calibration, "smoothing", default=base.smoothing)),
        deadzone=float(_pick(calibration, "deadzone", default=base.deadzone)),
        curl_lo=float(_pick(calibration, "curl_lo", default=base.curl_lo)),
        curl_hi=float(_pick(calibration, "curl_hi", default=base.curl_hi)),
        # Varios
        preview=_as_bool(_pick(runtime, "preview", default=base.preview), base.preview),
        debug=_as_bool(_pick(runtime, "debug", default=base.debug), base.debug),
        log_level=str(_pick(runtime, "log_level", default=base.log_level)).upper(),
        dry_run=base.dry_run,
        list_devices=base.list_devices,
        image=base.image,
    )
    settings.validate()
    return settings


def build_parser(defaults: Settings) -> argparse.ArgumentParser:
    d = defaults
    p = argparse.ArgumentParser(
        description="Control gestual de un carrito micro:bit por BLE UART.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    g = p.add_argument_group("Configuración")
    g.add_argument("--config", type=Path, default=DEFAULT_SETTINGS_PATH,
                   help="YAML de parámetros generales")
    g.add_argument("--gestures", type=Path, default=DEFAULT_GESTURES_PATH,
                   help="YAML de calibración gestual")

    g = p.add_argument_group("Bluetooth")
    g.add_argument("--address", default=d.address, help="dirección MAC del micro:bit")
    g.add_argument("--name", default=d.name, help="nombre BLE (alternativo a --address)")
    g.add_argument("--write-uuid", default=d.write_uuid, help="característica UART de escritura")
    g.add_argument("--notify-uuid", default=d.notify_uuid, help="característica UART de notificación")
    g.add_argument("--reconnect-min", type=float, default=d.reconnect_min,
                   help="espera inicial entre reconexiones BLE")
    g.add_argument("--reconnect-max", type=float, default=d.reconnect_max,
                   help="espera máxima entre reconexiones BLE")
    g.add_argument("--list-devices", action="store_true", help="escanear y listar dispositivos BLE")
    g.add_argument("--dry-run", action="store_true", help="no usar BLE (sólo visión)")

    g = p.add_argument_group("Cámara")
    g.add_argument("--camera", type=int, default=d.camera, help="índice de la webcam")
    g.add_argument("--width", type=int, default=d.width, help="ancho de captura")
    g.add_argument("--height", type=int, default=d.height, help="alto de captura")
    g.add_argument("--mirror", action=argparse.BooleanOptionalAction, default=d.mirror,
                   help="efecto espejo (más intuitivo)")
    g.add_argument("--preview", action=argparse.BooleanOptionalAction, default=d.preview,
                   help="mostrar ventana con vídeo y panel de estado")

    g = p.add_argument_group("Control")
    g.add_argument("--max-speed", type=int, default=d.max_speed, help="velocidad máxima (1-255)")
    g.add_argument("--step", type=int, default=d.step, help="histéresis de velocidad")
    g.add_argument("--min-interval", type=float, default=d.min_interval, help="s entre envíos BLE")
    g.add_argument("--heartbeat", type=float, default=d.heartbeat,
                   help="s entre reenvíos (keep-alive)")
    g.add_argument("--smoothing", type=float, default=d.smoothing, help="alfa del filtro EMA")
    g.add_argument("--deadzone", type=float, default=d.deadzone, help="zona muerta de extensión")
    g.add_argument("--curl-lo", type=float, default=d.curl_lo,
                   help="rectitud para 0 %% de extensión")
    g.add_argument("--curl-hi", type=float, default=d.curl_hi,
                   help="rectitud para 100 %% de extensión")
    g.add_argument("--lost-grace", type=float, default=d.lost_grace,
                   help="s de gracia al perder la mano")
    g.add_argument("--swap-hands", action=argparse.BooleanOptionalAction, default=d.swap_hands,
                   help="invertir izquierda/derecha si la etiqueta sale al revés")
    g.add_argument("--single-hand", choices=("own", "both"), default=d.single_hand,
                   help="con una sola mano visible: 'own' mueve sólo su rueda, 'both' mueve las dos")

    g = p.add_argument_group("Depuración")
    g.add_argument("--model", type=Path, default=d.model, help="ruta del modelo .task")
    g.add_argument("--image", type=Path, default=d.image,
                   help="procesar una imagen fija y mostrar métricas")
    g.add_argument("--debug", action="store_true", default=d.debug,
                   help="mostrar métricas crudas en el panel")
    g.add_argument("--log-level", default=d.log_level, help="DEBUG, INFO, WARNING, ERROR")
    return p


def parse_args(argv: list[str] | None = None) -> Settings:
    """Carga los YAML y aplica los flags de CLI como sobrescritura.

    Primero se leen las rutas ``--config``/``--gestures`` (si existen), se
    construye el parser con esos valores como defaults y, por último, se
    sustituyen únicamente los campos presentes en el namespace resultante.
    """
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", type=Path, default=DEFAULT_SETTINGS_PATH)
    pre.add_argument("--gestures", type=Path, default=DEFAULT_GESTURES_PATH)
    known, _ = pre.parse_known_args(argv)

    defaults = load_settings(known.config, known.gestures)
    ns = build_parser(defaults).parse_args(argv)
    values = vars(ns)
    values.pop("config", None)
    values.pop("gestures", None)
    settings = Settings(**values)
    settings.validate()
    return settings

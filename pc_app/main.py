# -*- coding: utf-8 -*-
"""Punto de entrada: visión, control y BLE.

Uso:
    python main.py                       # control normal
    python main.py --dry-run             # sin BLE (sólo visión)
    python main.py --list-devices        # escanear dispositivos BLE
    python main.py --image foto.jpg      # calibrar métricas con una foto
    python main.py --help
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from bleak import BleakScanner

from pc_app.application.car_controller import CarController
from pc_app.application.config_panel import ConfigurationPanelController
from pc_app.config import Settings, parse_args
from pc_app.domain.entities.wheel_command import WheelCommand
from pc_app.domain.interfaces.command_sender import ICommandSender
from pc_app.infrastructure.ble_uart import BleUartSender
from pc_app.infrastructure.camera import FrameGrabber
from pc_app.infrastructure.config_store import YamlConfigStore
from pc_app.infrastructure.dry_run_sender import DryRunCommandSender
from pc_app.infrastructure.mediapipe_tracker import MediaPipeHandTracker
from pc_app.infrastructure.model_loader import ensure_model
from pc_app.presentation.overlay import H, W, handle_key, handle_mouse, render
from pc_app.presentation.window import PreviewWindow
from pc_app.presentation.web_dashboard import WebDashboard

LOG = logging.getLogger("gesture-cart")

SIDES = ("L", "R")


def build_config_panel(settings: Settings) -> ConfigurationPanelController:
    """Crea el controlador de eventos del panel de Configuración.

    Los ``set_*`` persisten cada cambio validado en ambos YAML y lo aplican
    al ``Settings`` en memoria.
    """
    return ConfigurationPanelController(YamlConfigStore(), settings)


def _build_sender(cfg: Settings) -> ICommandSender:
    if cfg.dry_run:
        return DryRunCommandSender()
    return BleUartSender(cfg)


async def run(cfg: Settings) -> int:
    """Bucle principal: captura -> inferencia -> control -> BLE/preview."""
    grabber = FrameGrabber(cfg.camera, cfg.width, cfg.height)
    try:
        tracker = MediaPipeHandTracker(cfg)
    except Exception:
        grabber.stop()
        raise
    grabber.start()

    controller = CarController(cfg, _build_sender(cfg))

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    dashboard = WebDashboard(cfg.web_port) if cfg.preview and cfg.web_ui else None
    window = PreviewWindow() if cfg.preview and dashboard is None else None
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision")
    last_seq = -1
    panel = build_config_panel(cfg) if cfg.preview else None

    LOG.info(
        "Listo. q/ESC: salir · h: invertir manos · f: pantalla completa."
        if cfg.preview
        else "Listo. Sin ventana: Ctrl+C para salir."
    )
    try:
        if dashboard is not None:
            dashboard.start()
        controller.start()
        while not stop.is_set():
            frame, seq = grabber.latest()
            if frame is None or seq == last_seq:
                await asyncio.sleep(0.004)
                continue
            last_seq = seq
            if cfg.mirror:
                frame = cv2.flip(frame, 1)

            # La inferencia corre fuera del event loop para no frenar el BLE.
            poses = await loop.run_in_executor(executor, tracker.process, frame)
            controller.update(poses)

            if dashboard is not None:
                for item in dashboard.take_actions():
                    try:
                        if item["type"] == "config":
                            setters = {
                                "deadzone": panel.set_deadzone,
                                "smoothing": panel.set_smoothing,
                                "step": panel.set_step,
                                "lost_grace": panel.set_lost_grace,
                                "speed_multiplier": panel.set_speed_multiplier,
                            }
                            setters[item["key"]](item["value"])
                        elif item["action"] == "toggle_running":
                            controller.set_enabled(not controller.enabled)
                        elif item["action"] == "toggle_hands":
                            controller.toggle_hands()
                        elif item["action"] == "exit":
                            stop.set()
                    except Exception as exc:
                        LOG.warning("No se pudo aplicar el cambio web: %s", exc)
                dashboard.publish(frame, poses, controller.sender, controller, cfg, grabber.fps)

            if window is not None:
                hover = None
                if window.mouse_position is not None:
                    client_w, client_h = window.client_size()
                    hover = (
                        round(window.mouse_position[0] * W / max(1, client_w)),
                        round(window.mouse_position[1] * H / max(1, client_h)),
                    )
                key = window.show(render(
                    frame, poses, controller.sender, grabber.fps, cfg,
                    controller.last_payload, panel=panel,
                    running=controller.enabled,
                    hover=hover,
                ))
                if key in (27, ord("q")):
                    break
                consumed = False
                if panel is not None:
                    try:
                        consumed = handle_key(key, panel)
                    except Exception as exc:
                        LOG.warning("No se pudo guardar el valor: %s", exc)
                if not consumed:
                    if key == ord("h"):
                        controller.toggle_hands()
                    elif key == ord("f"):
                        window.toggle_fullscreen()
                mouse = window.take_mouse_event()
                if mouse is not None:
                    client_w, client_h = window.client_size()
                    mouse_x = round(mouse[0] * W / max(1, client_w))
                    mouse_y = round(mouse[1] * H / max(1, client_h))
                    try:
                        handle_mouse(mouse_x, mouse_y, panel, controller)
                    except Exception as exc:
                        LOG.warning("No se pudo aplicar la configuración: %s", exc)
                if not window.is_open():
                    break
    finally:
        stop.set()
        executor.shutdown(wait=False, cancel_futures=True)
        grabber.stop()
        grabber.join(timeout=1.0)
        if window is not None:
            window.close()
        if dashboard is not None:
            dashboard.close()
        tracker.close()
        await controller.stop()  # parada de seguridad al salir
    return 0


async def list_devices(timeout: float = 8.0) -> int:
    LOG.info("Escaneando dispositivos BLE (%.0f s)...", timeout)
    devices = await BleakScanner.discover(timeout=timeout)
    if not devices:
        print("No se encontró ningún dispositivo BLE.")
        return 1
    for device in devices:
        rssi = getattr(device, "rssi", "?")
        print(f"{device.address}   rssi={rssi}   {device.name or '(sin nombre)'}")
    return 0


def run_image(cfg: Settings, path: Path) -> int:
    """Procesa una imagen fija y muestra las métricas (útil para calibrar)."""
    frame = cv2.imread(str(path))
    if frame is None:
        LOG.error("No se pudo leer la imagen: %s", path)
        return 2
    if cfg.mirror:  # misma vista que el bucle en vivo
        frame = cv2.flip(frame, 1)

    tracker = MediaPipeHandTracker(cfg)
    try:
        poses = tracker.process(frame)
    finally:
        tracker.close()

    if not poses:
        print("Sin manos detectadas en la imagen.")
        return 1

    for side in SIDES:
        pose = poses.get(side)
        label = "izquierda" if side == "L" else "derecha"
        if pose is None:
            print(f"{label:10s}: no detectada")
            continue
        print(
            f"{label:10s}: posición de muñeca={pose.raw_index:+.3f} | "
            f"velocidad={pose.speed(cfg.max_speed, cfg.deadzone, cfg.speed_multiplier):+.0f}"
        )

    command = WheelCommand.from_speeds(
        poses["L"].speed(cfg.max_speed, cfg.deadzone, cfg.speed_multiplier) if "L" in poses else 0.0,
        poses["R"].speed(cfg.max_speed, cfg.deadzone, cfg.speed_multiplier) if "R" in poses else 0.0,
        step=cfg.step,
        max_speed=cfg.max_speed,
    )
    print(f"\ncomando: {' | '.join(command.messages())}  (mensajes BLE separados)")
    print("Si 'izquierda' y 'derecha' están cambiadas, añade --swap-hands.")
    print("Ajusta --deadzone para cambiar el ancho de STOP.")
    return 0


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    if cfg.list_devices:
        try:
            return asyncio.run(list_devices())
        except KeyboardInterrupt:
            return 130

    ensure_model(cfg.model)

    if cfg.image is not None:
        return run_image(cfg, cfg.image)

    try:
        return asyncio.run(run(cfg))
    except KeyboardInterrupt:
        LOG.warning("Interrumpido por el usuario")
        return 130
    except RuntimeError as exc:  # cámara no disponible, etc.
        LOG.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

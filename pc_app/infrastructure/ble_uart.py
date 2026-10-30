# -*- coding: utf-8 -*-
"""Enlace UART BLE (Nordic NUS) con cola de tamaño 1 y reconexión."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from pc_app.config import Settings
from pc_app.domain.interfaces.command_sender import ICommandSender

LOG = logging.getLogger("gesture-cart.ble")

CHUNK = 20  # bytes por escritura


class BleUartSender(ICommandSender):
    """Enlace UART BLE asíncrono con reconexión automática.

    - ``send()`` nunca bloquea: si hay una orden pendiente se sustituye.
    - Un único task supervisor gestiona conexión, escritura y reconexión,
      de modo que el bucle de visión nunca se queda esperando al Bluetooth.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: asyncio.Queue[tuple[str, ...]] = asyncio.Queue(maxsize=1)
        self._client: BleakClient | None = None
        self._task: asyncio.Task | None = None
        self._closing = False
        self._close_event = asyncio.Event()
        self._backoff = settings.reconnect_min
        self._connected = False
        self._sent = 0
        self._dropped = 0
        self._last_error: str | None = None

    # -- propiedades de ICommandSender --------------------------------------
    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def sent(self) -> int:
        return self._sent

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def last_error(self) -> str | None:
        return self._last_error

    # -- ciclo de vida -------------------------------------------------------
    def start(self) -> None:
        self._task = asyncio.create_task(self._supervisor(), name="ble-link")

    async def close(self, final: str | None = "z") -> None:
        self._closing = True
        self._close_event.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._client is not None:
            if final and self._client.is_connected:
                with contextlib.suppress(Exception):
                    await self._write(final)
            with contextlib.suppress(Exception):
                await self._client.disconnect()
        self._client = None
        self._connected = False

    # -- API pública ---------------------------------------------------------
    def send(self, messages: tuple[str, ...]) -> None:
        """Encola una orden descartando la anterior si aún no se ha enviado.

        La tupla conserva un mensaje por rueda; se escribirá completa en
        escrituras BLE separadas (primero ``L``, después ``R``).
        """
        if self._closing:
            return
        try:
            self._queue.put_nowait(messages)
            return
        except asyncio.QueueFull:
            pass
        with contextlib.suppress(asyncio.QueueEmpty):
            self._queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(messages)
        self._dropped += 1

    # -- internos ------------------------------------------------------------
    async def _sleep(self, delay: float) -> None:
        """Sleep cancelable: se interrumpe si se cierra la aplicación."""
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._close_event.wait(), timeout=delay)

    async def _resolve(self):
        if not self._settings.name:
            return self._settings.address
        device = await BleakScanner.find_device_by_name(self._settings.name, timeout=10.0)
        if device is None:
            raise BleakError(f"no se encontró el dispositivo BLE '{self._settings.name}'")
        return device

    async def _connect(self) -> bool:
        settings = self._settings
        target = settings.name or settings.address
        LOG.info("Conectando a %s ...", target)
        try:
            client = BleakClient(
                await self._resolve(),
                disconnected_callback=self._on_disconnect,
                timeout=15.0,
            )
            await client.connect()
            with contextlib.suppress(Exception):  # algunas variantes no notifican
                await client.start_notify(settings.notify_uuid, self._on_notify)
            self._client = client
            self._connected = True
            self._last_error = None
            self._backoff = settings.reconnect_min
            LOG.info("BLE conectado (%s)", target)
            return True
        except (BleakError, OSError, asyncio.TimeoutError) as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._client = None
            self._connected = False
            LOG.warning(
                "BLE no disponible (%s). Reintento en %.1f s",
                self._last_error, self._backoff,
            )
            return False

    async def _write(self, payload: str | tuple[str, ...]) -> bool:
        client = self._client
        if client is None or not client.is_connected:
            self._connected = False
            return False
        # Un mensaje por rueda: el firmware no acepta "R150,L150" junto.
        messages = (payload,) if isinstance(payload, str) else payload
        try:
            for index, message in enumerate(messages):
                data = (message.strip() + "\n").encode("utf-8")
                for offset in range(0, len(data), CHUNK):
                    await client.write_gatt_char(
                        self._settings.write_uuid,
                        data[offset:offset + CHUNK],
                        response=False,
                    )
                    if offset + CHUNK < len(data):
                        await asyncio.sleep(0.01)  # respiro entre paquetes
                if index + 1 < len(messages):
                    await asyncio.sleep(0.01)  # separa los mensajes por rueda
        except (BleakError, OSError) as exc:
            LOG.warning("Fallo al escribir por BLE: %s", exc)
            self._connected = False
            with contextlib.suppress(Exception):
                await client.disconnect()
            self._client = None
            return False

        self._sent += 1
        LOG.debug("-> %s", " ".join(messages))
        return True

    async def _supervisor(self) -> None:
        while not self._closing:
            if not self._connected:
                if not await self._connect():
                    await self._sleep(self._backoff)
                    self._backoff = min(self._backoff * 2, self._settings.reconnect_max)
                    continue

            try:
                payload = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._write(payload)

    # -- callbacks de bleak --------------------------------------------------
    def _on_disconnect(self, _client: BleakClient) -> None:
        if self._connected:
            LOG.warning("BLE desconectado; se intentará reconectar")
        self._connected = False

    def _on_notify(self, _sender, data: bytearray) -> None:
        text = data.decode("utf-8", errors="ignore").strip()
        if text:
            LOG.info("<- micro:bit: %s", text)

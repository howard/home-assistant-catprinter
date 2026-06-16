"""BLE transport for the cat printer, built on Home Assistant's Bluetooth stack.

We deliberately do not drive ``bleak`` directly. Instead we resolve the
``BLEDevice`` from Home Assistant's Bluetooth manager and connect via
``bleak-retry-connector`` (both bundled with HA core), so connections cooperate
with the rest of the system and benefit from retry/backoff handling.
"""
from __future__ import annotations

import asyncio
import logging

import numpy as np
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import commands
from .const import (
    PRINTER_READY_NOTIFICATION,
    RX_CHARACTERISTIC_UUID,
    TX_CHARACTERISTIC_UUID,
    WAIT_AFTER_EACH_CHUNK_S,
    WAIT_FOR_PRINTER_DONE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class CatPrinterError(Exception):
    """Raised when a print job cannot be completed."""


class CatPrinter:
    """Owns the BLE conversation with a single cat printer."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        self._hass = hass
        self._address = address
        self._name = name
        # Serialize jobs: the printer can only handle one at a time.
        self._lock = asyncio.Lock()

    @property
    def address(self) -> str:
        return self._address

    @property
    def name(self) -> str:
        return self._name

    async def print_rows(self, rows: np.ndarray, energy: int) -> None:
        """Encode ``rows`` (True == black) and send the job over BLE."""
        data = commands.cmds_print_img(rows, energy=energy)
        async with self._lock:
            await self._send(data, wait_for_done=True)

    async def keep_alive(self) -> None:
        """Send a harmless state query to keep the printer from powering off.

        This must never raise: the printer is often briefly out of range or
        asleep, which is expected and not actionable, so failures are logged at
        debug level only.
        """
        async with self._lock:
            try:
                await self._send(
                    bytes(commands.CMD_GET_DEV_STATE), wait_for_done=False
                )
                _LOGGER.debug("Sent keep-alive ping to %s", self._name)
            except Exception as err:  # noqa: BLE001 - keep-alive is best-effort
                _LOGGER.debug(
                    "Keep-alive ping to %s skipped: %s", self._name, err
                )

    async def _send(self, data: bytes, wait_for_done: bool) -> None:
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device is None:
            raise CatPrinterError(
                f"Printer {self._name} ({self._address}) was not found; "
                "make sure it is powered on and in range."
            )

        done = asyncio.Event()

        def _on_notify(_char: BleakGATTCharacteristic, payload: bytearray) -> None:
            _LOGGER.debug("Notification from %s: %s", self._name, payload.hex())
            if bytes(payload) == PRINTER_READY_NOTIFICATION:
                done.set()

        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, self._name
        )
        try:
            chunk_size = max((client.mtu_size or 23) - 3, 20)
            if wait_for_done:
                await client.start_notify(RX_CHARACTERISTIC_UUID, _on_notify)
            _LOGGER.debug(
                "Sending %d bytes to %s in %d-byte chunks",
                len(data),
                self._name,
                chunk_size,
            )
            for offset in range(0, len(data), chunk_size):
                await client.write_gatt_char(
                    TX_CHARACTERISTIC_UUID, data[offset : offset + chunk_size]
                )
                await asyncio.sleep(WAIT_AFTER_EACH_CHUNK_S)

            if wait_for_done:
                try:
                    await asyncio.wait_for(
                        done.wait(), timeout=WAIT_FOR_PRINTER_DONE_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    # The data was sent; the printer just never acked. Most
                    # prints still come out, so warn rather than fail the call.
                    _LOGGER.warning(
                        "Timed out waiting for %s to report the print finished",
                        self._name,
                    )
        finally:
            with _suppress_disconnect_errors():
                await client.disconnect()


class _suppress_disconnect_errors:
    """Context manager that swallows errors raised while disconnecting."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            _LOGGER.debug("Ignoring error during disconnect: %s", exc)
        return True

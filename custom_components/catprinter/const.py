"""Constants for the Cat Printer integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "catprinter"

# Config entry data keys.
CONF_ADDRESS: Final = "address"

# BLE service UUIDs advertised by cat printers. macOS reports 0xaf30 while
# Linux/BlueZ reports 0xae30; we match both. (From rbaron/catprinter.)
SERVICE_UUIDS: Final = (
    "0000ae30-0000-1000-8000-00805f9b34fb",
    "0000af30-0000-1000-8000-00805f9b34fb",
)

# GATT characteristics (identical across known models).
TX_CHARACTERISTIC_UUID: Final = "0000ae01-0000-1000-8000-00805f9b34fb"
RX_CHARACTERISTIC_UUID: Final = "0000ae02-0000-1000-8000-00805f9b34fb"

# The printer emits this notification when it has finished a print job.
PRINTER_READY_NOTIFICATION: Final = b"\x51\x78\xae\x01\x01\x00\x00\x00\xff"

# Advertised name prefixes used to recognise printers during manual setup.
KNOWN_NAME_PREFIXES: Final = ("GB", "GT", "MX", "YT", "FT")

# Pause between BLE chunk writes (seconds), and timeout awaiting the done event.
WAIT_AFTER_EACH_CHUNK_S: Final = 0.02
WAIT_FOR_PRINTER_DONE_TIMEOUT: Final = 30.0

# Default thermal energy (0x0000 lightest .. 0xffff darkest).
DEFAULT_ENERGY: Final = 0xFFFF
MAX_ENERGY: Final = 0xFFFF

# Service names and field attributes.
SERVICE_PRINT_IMAGE: Final = "print_image"
SERVICE_PRINT_TEXT: Final = "print_text"

ATTR_IMAGE: Final = "image"
ATTR_MESSAGE: Final = "message"
ATTR_ENERGY: Final = "energy"
ATTR_DITHER: Final = "dither"
ATTR_FONT_SIZE: Final = "font_size"

DEFAULT_FONT_SIZE: Final = 24

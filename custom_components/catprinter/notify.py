"""Notify entity and print services for the Cat Printer integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import imaging
from .const import (
    ATTR_DITHER,
    ATTR_ENERGY,
    ATTR_FONT_SIZE,
    ATTR_IMAGE,
    ATTR_MESSAGE,
    DEFAULT_ENERGY,
    DEFAULT_FONT_SIZE,
    DOMAIN,
    MAX_ENERGY,
    SERVICE_PRINT_IMAGE,
    SERVICE_PRINT_TEXT,
)
from .printer import CatPrinter, CatPrinterError

_LOGGER = logging.getLogger(__name__)

_ENERGY = vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_ENERGY))

PRINT_IMAGE_SCHEMA = {
    vol.Required(ATTR_IMAGE): cv.string,
    vol.Optional(ATTR_ENERGY, default=DEFAULT_ENERGY): _ENERGY,
    vol.Optional(ATTR_DITHER, default=imaging.DITHER_FLOYD_STEINBERG): vol.In(
        imaging.DITHER_OPTIONS
    ),
}

PRINT_TEXT_SCHEMA = {
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_ENERGY, default=DEFAULT_ENERGY): _ENERGY,
    vol.Optional(ATTR_FONT_SIZE, default=DEFAULT_FONT_SIZE): vol.All(
        vol.Coerce(int), vol.Range(min=8, max=120)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the notify entity and register the print services."""
    printer: CatPrinter = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CatPrinterNotifyEntity(printer, entry)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PRINT_IMAGE, PRINT_IMAGE_SCHEMA, "async_print_image"
    )
    platform.async_register_entity_service(
        SERVICE_PRINT_TEXT, PRINT_TEXT_SCHEMA, "async_print_text"
    )


class CatPrinterNotifyEntity(NotifyEntity):
    """A notify target that prints text on the thermal printer."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:printer"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, printer: CatPrinter, entry: ConfigEntry) -> None:
        self._printer = printer
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, printer.address)},
            connections={(dr.CONNECTION_BLUETOOTH, printer.address)},
            name=entry.title,
            manufacturer="rbaron / cat printer",
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Print ``message`` (and optional ``title``) as text."""
        text = f"{title}\n{message}" if title else message
        await self.async_print_text(message=text)

    async def async_print_text(
        self,
        message: str,
        energy: int = DEFAULT_ENERGY,
        font_size: int = DEFAULT_FONT_SIZE,
    ) -> None:
        """Render text to a bitmap and print it."""
        rows = await self.hass.async_add_executor_job(
            imaging.text_to_rows, message, font_size
        )
        await self._print(rows, energy)

    async def async_print_image(
        self,
        image: str,
        energy: int = DEFAULT_ENERGY,
        dither: str = imaging.DITHER_FLOYD_STEINBERG,
    ) -> None:
        """Fetch an image (URL or allow-listed path) and print it."""
        data = await imaging.async_fetch_image(self.hass, image)
        rows = await self.hass.async_add_executor_job(
            imaging.image_to_rows, data, dither
        )
        await self._print(rows, energy)

    async def _print(self, rows, energy: int) -> None:
        try:
            await self._printer.print_rows(rows, energy)
        except CatPrinterError as err:
            raise HomeAssistantError(str(err)) from err

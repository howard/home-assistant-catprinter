"""The Cat Printer integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from homeassistant.components import bluetooth

from .const import DOMAIN
from .printer import CatPrinter

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.NOTIFY]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cat Printer from a config entry."""
    address: str = entry.data[CONF_ADDRESS]

    # Surface a clear "not ready" state if the radio can't see the printer yet.
    # The BLEDevice is resolved again lazily at print time, so transient absence
    # after setup is fine.
    if not bluetooth.async_address_present(hass, address, connectable=True):
        _LOGGER.debug(
            "Printer %s not currently visible; will connect on demand", address
        )

    printer = CatPrinter(hass, address, entry.title)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = printer

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

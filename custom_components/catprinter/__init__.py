"""The Cat Printer integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.components import bluetooth

from .const import CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL, DOMAIN
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

    # Keep the printer awake: periodically send a harmless state query so it
    # doesn't auto-power-off while idle.
    interval = entry.options.get(CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL)

    async def _async_keep_alive(_now) -> None:
        await printer.keep_alive()

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_keep_alive, timedelta(seconds=interval)
        )
    )
    # Re-run setup (picking up a new interval) when options change.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

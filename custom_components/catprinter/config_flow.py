"""Config flow for the Cat Printer integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_KEEPALIVE_INTERVAL,
    DEFAULT_KEEPALIVE_INTERVAL,
    DOMAIN,
    KNOWN_NAME_PREFIXES,
    MAX_KEEPALIVE_INTERVAL,
    MIN_KEEPALIVE_INTERVAL,
    SERVICE_UUIDS,
)


def _looks_like_printer(info: BluetoothServiceInfoBleak) -> bool:
    """Return True if a discovered device looks like a cat printer."""
    if any(uuid in info.service_uuids for uuid in SERVICE_UUIDS):
        return True
    name = info.name or ""
    return name.startswith(KNOWN_NAME_PREFIXES)


class CatPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cat Printer."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        # address -> human readable label, for the manual picker.
        self._discovered: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return CatPrinterOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered printer."""
        assert self._discovery is not None
        name = self._discovery.name or "Cat Printer"
        if user_input is not None:
            return self.async_create_entry(
                title=name, data={CONF_ADDRESS: self._discovery.address}
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup by picking from discovered devices."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered.get(address, "Cat Printer"),
                data={CONF_ADDRESS: address},
            )

        current = self._async_current_ids()
        self._discovered = {
            info.address: f"{info.name or 'Cat Printer'} ({info.address})"
            for info in async_discovered_service_info(self.hass)
            if _looks_like_printer(info) and info.address not in current
        }

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered)}
            ),
        )


class CatPrinterOptionsFlow(OptionsFlow):
    """Handle Cat Printer options (keep-alive interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_KEEPALIVE_INTERVAL, default=current
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_KEEPALIVE_INTERVAL, max=MAX_KEEPALIVE_INTERVAL
                        ),
                    )
                }
            ),
        )

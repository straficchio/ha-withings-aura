"""Config flow for the Withings Aura integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_FIRMWARE,
    CONF_MAC,
    CONF_POLL_INTERVAL,
    CONF_SLOW_POLL_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLOW_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MAX_SLOW_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    MIN_SLOW_POLL_INTERVAL,
)
from .device import AuraDevice
from .exceptions import AuraError
from .protocol import ProbeChallengeError
from .transport import AuraBridge
from .util import normalize_mac

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)
        ),
        vol.Optional(CONF_SLOW_POLL_INTERVAL, default=DEFAULT_SLOW_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_SLOW_POLL_INTERVAL, max=MAX_SLOW_POLL_INTERVAL)
        ),
    }
)


async def async_probe(host: str, port: int) -> Any:
    """Connect and probe a unit, always closing the bridge."""
    bridge = AuraBridge(host, port)
    try:
        await bridge.async_connect()
        return await AuraDevice(bridge).probe()
    finally:
        await bridge.async_close()


class AuraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a Withings Aura."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: dict[str, Any] | None = None

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Handle mDNS discovery."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        properties = discovery_info.properties or {}
        mac = normalize_mac(str(properties.get(CONF_MAC, "")))
        firmware = properties.get(CONF_FIRMWARE)
        if not mac:
            try:
                probe = await async_probe(host, port)
            except ProbeChallengeError:
                return self.async_abort(reason="unsupported_auth")
            except AuraError:
                return self.async_abort(reason="cannot_connect")
            mac = normalize_mac(probe.mac)
            firmware = str(probe.firmware)
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
        self._discovery = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_MAC: mac,
            CONF_FIRMWARE: firmware,
        }
        self.context["title_placeholders"] = {
            "name": DEFAULT_NAME,
            "host": host,
            "mac": mac,
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm an mDNS-discovered unit."""
        if user_input is not None and self._discovery is not None:
            return await self._async_create_entry(self._discovery)
        assert self._discovery is not None
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": DEFAULT_NAME,
                "host": self._discovery[CONF_HOST],
                "mac": self._discovery[CONF_MAC],
            },
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            try:
                probe = await async_probe(host, port)
            except ProbeChallengeError:
                errors["base"] = "unsupported_auth"
            except AuraError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error probing Aura")
                errors["base"] = "unknown"
            else:
                mac = normalize_mac(probe.mac)
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return await self._async_create_entry(
                    {
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_MAC: mac,
                        CONF_FIRMWARE: str(probe.firmware),
                    }
                )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the bridge host or port."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            try:
                probe = await async_probe(host, port)
            except ProbeChallengeError:
                errors["base"] = "unsupported_auth"
            except AuraError:
                errors["base"] = "cannot_connect"
            else:
                mac = normalize_mac(probe.mac)
                if mac != entry.unique_id:
                    errors["base"] = "wrong_device"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={CONF_HOST: host, CONF_PORT: port},
                    )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                    vol.Optional(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                }
            ),
            errors=errors,
        )

    async def _async_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(title=DEFAULT_NAME, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AuraOptionsFlow()


class AuraOptionsFlow(OptionsFlow):
    """Options for polling intervals."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                ),
                vol.Optional(
                    CONF_SLOW_POLL_INTERVAL,
                    default=options.get(CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_INTERVAL),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SLOW_POLL_INTERVAL, max=MAX_SLOW_POLL_INTERVAL),
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

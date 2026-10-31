"""The Withings Aura integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntryError, ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HOST,
    CONF_POLL_INTERVAL,
    CONF_PORT,
    CONF_SLOW_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SLOW_POLL_INTERVAL,
)
from .coordinator import AuraCoordinator
from .device import AuraDevice
from .exceptions import AuraError
from .protocol import ProbeChallengeError
from .runtime import AuraConfigEntry, AuraRuntimeData
from .services import async_register_services
from .transport import AuraBridge
from .util import normalize_mac

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide services."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AuraConfigEntry) -> bool:
    """Set up one Aura from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    bridge = AuraBridge(host, port)
    try:
        await bridge.async_connect()
        device = AuraDevice(bridge)
        probe = await device.probe()
    except ProbeChallengeError as err:
        await bridge.async_close(disconnect=False)
        raise ConfigEntryError(
            "This Aura requires the Withings association secret; local control is unavailable"
        ) from err
    except AuraError as err:
        await bridge.async_close(disconnect=False)
        raise ConfigEntryNotReady(str(err)) from err

    if normalize_mac(probe.mac) != entry.unique_id:
        await bridge.async_close(disconnect=False)
        raise ConfigEntryError(f"Device MAC mismatch: expected {entry.unique_id}, got {probe.mac}")

    coordinator = AuraCoordinator(
        hass,
        entry,
        device,
        poll_interval=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        slow_poll_interval=entry.options.get(CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = AuraRuntimeData(
        bridge=bridge,
        device=device,
        coordinator=coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AuraConfigEntry) -> bool:
    """Unload one Aura."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.bridge.async_close()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: AuraConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)

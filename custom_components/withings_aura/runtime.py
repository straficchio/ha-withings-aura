"""Runtime data and typed config entry for Withings Aura."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import AuraCoordinator
from .device import AuraDevice
from .transport import AuraBridge


@dataclass(slots=True)
class AuraRuntimeData:
    """Objects stored on the config entry."""

    bridge: AuraBridge
    device: AuraDevice
    coordinator: AuraCoordinator


AuraConfigEntry = ConfigEntry[AuraRuntimeData]

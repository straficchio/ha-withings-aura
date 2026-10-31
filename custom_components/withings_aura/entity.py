"""Base entity for the Withings Aura integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import AuraCoordinator


class AuraEntity(CoordinatorEntity[AuraCoordinator]):
    """Base class for all Aura entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AuraCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.coordinator.config_entry.unique_id
                    or self.coordinator.config_entry.entry_id,
                )
            },
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.coordinator.config_entry.title,
            sw_version=str(data.probe.firmware) if data else None,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

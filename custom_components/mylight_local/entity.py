"""Entité de base."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MyLightDevice
from .const import DEVICE_LABELS, DOMAIN, MANUFACTURER, UNAVAILABLE_STATUSES
from .coordinator import MyLightCoordinator


class MyLightEntity(CoordinatorEntity[MyLightCoordinator]):
    """Entité rattachée à un équipement MyLight."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MyLightCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        device = coordinator.data[key]
        label = DEVICE_LABELS.get(device.device_type, device.device_type or "Équipement")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, key)},
            name=f"{label} {key[-4:]}",
            manufacturer=MANUFACTURER,
            model=label,
            sw_version=device.firmware,
            serial_number=key,
        )

    @property
    def device(self) -> MyLightDevice | None:
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        device = self.device
        return (
            super().available
            and device is not None
            and device.status not in UNAVAILABLE_STATUSES
        )


class MyLightSiteEntity(CoordinatorEntity[MyLightCoordinator]):
    """Entité « installation » (production, réseau, consommation maison)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MyLightCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"site_{entry_id}")},
            name="Installation MyLight",
            manufacturer=MANUFACTURER,
            model="Site",
        )

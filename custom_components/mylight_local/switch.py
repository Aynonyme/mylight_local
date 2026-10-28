"""Interrupteurs pour les prises commandables (ETH, SW, TPH)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NON_CONTROLLABLE_TYPES
from .coordinator import MyLightConfigEntry, MyLightCoordinator
from .entity import MyLightEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [
            MyLightSwitch(coordinator, key)
            for key, device in coordinator.data.items()
            if key not in known and device.device_type not in NON_CONTROLLABLE_TYPES
        ]
        known.update(sw._key for sw in new)
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class MyLightSwitch(MyLightEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_name = None  # entité principale de l'appareil

    def __init__(self, coordinator: MyLightCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self._attr_unique_id = f"{key}_switch"

    @property
    def is_on(self) -> bool | None:
        device = self.device
        return device.state if device else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_state(self.device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_state(self.device, False)

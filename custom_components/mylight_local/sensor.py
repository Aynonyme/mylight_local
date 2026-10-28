"""Capteurs : puissance, énergie (intégrée), statut."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import MyLightDevice
from .coordinator import MyLightConfigEntry, MyLightCoordinator
from .const import CONF_PRODUCTION_DEVICE, UNAVAILABLE_STATUSES
from .entity import MyLightEntity, MyLightSiteEntity

PARALLEL_UPDATES = 0

# Au-delà de cet intervalle entre deux mesures, on n'intègre pas (trou de données).
MAX_INTEGRATION_GAP = 300.0


@dataclass(frozen=True, kw_only=True)
class MyLightSensorDescription(SensorEntityDescription):
    value_fn: Callable[[MyLightDevice], float | str | None]
    exists_fn: Callable[[MyLightDevice], bool] = lambda _d: True


def _phase(i: int) -> Callable[[MyLightDevice], float | None]:
    return lambda d: d.phases[i] if d.phases else None


def _power_desc(key: str, value_fn, exists_fn) -> MyLightSensorDescription:
    return MyLightSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=value_fn,
        exists_fn=exists_fn,
    )


SENSORS: tuple[MyLightSensorDescription, ...] = (
    _power_desc("power", lambda d: d.total_power, lambda d: d.total_power is not None),
    *(
        _power_desc(f"power_p{i + 1}", _phase(i), lambda d: d.phases is not None)
        for i in range(3)
    ),
    MyLightSensorDescription(
        key="status",
        translation_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new: list[SensorEntity] = []
        for key, device in coordinator.data.items():
            for desc in SENSORS:
                uid = f"{key}_{desc.key}"
                if uid not in known and desc.exists_fn(device):
                    known.add(uid)
                    new.append(MyLightSensor(coordinator, key, desc))
            if device.total_power is not None:
                if device.device_type == "GMD":
                    specs = (("energy_import", 1), ("energy_export", -1))
                else:
                    specs = (("energy", 1),)
                for ekey, sign in specs:
                    uid = f"{key}_{ekey}"
                    if uid not in known:
                        known.add(uid)
                        new.append(MyLightEnergySensor(coordinator, key, ekey, sign))
        prod_key = entry.options.get(CONF_PRODUCTION_DEVICE)
        if prod_key and prod_key in coordinator.data:
            has_grid = any(d.device_type == "GMD" for d in coordinator.data.values())
            wanted = [("production_power", MyLightSitePowerSensor),
                      ("production_energy", MyLightSiteEnergySensor)]
            if has_grid:
                wanted += [("grid_power", MyLightSitePowerSensor),
                           ("house_power", MyLightSitePowerSensor),
                           ("house_energy", MyLightSiteEnergySensor)]
            for kind, cls in wanted:
                uid = f"{entry.entry_id}_{kind}"
                if uid not in known:
                    known.add(uid)
                    new.append(cls(coordinator, entry.entry_id, prod_key, kind))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class MyLightSensor(MyLightEntity, SensorEntity):
    entity_description: MyLightSensorDescription

    def __init__(
        self,
        coordinator: MyLightCoordinator,
        key: str,
        description: MyLightSensorDescription,
    ) -> None:
        super().__init__(coordinator, key)
        self.entity_description = description
        self._attr_unique_id = f"{key}_{description.key}"

    @property
    def available(self) -> bool:
        # Le statut reste visible même quand l'appareil est hors ligne.
        if self.entity_description.key == "status":
            return self.coordinator.last_update_success and self.device is not None
        return super().available

    @property
    def native_value(self) -> float | str | None:
        device = self.device
        return self.entity_description.value_fn(device) if device else None


class _Integrator:
    """Intégration trapézoïdale d'une puissance (W) en kWh, avec restauration."""

    _total: float = 0.0
    _last_power: float | None = None
    _last_time: float | None = None

    async def _restore_total(self) -> None:
        if (last := await self.async_get_last_sensor_data()) is not None:
            try:
                self._total = float(last.native_value)
            except (TypeError, ValueError):
                self._total = 0.0

    def _integrate(self, power: float | None) -> None:
        if power is None:  # indisponible : on coupe l'intégration (pas de trou comblé)
            self._last_power = self._last_time = None
            return
        now = time.monotonic()
        if self._last_time is not None and self._last_power is not None:
            dt = now - self._last_time
            if 0 < dt <= MAX_INTEGRATION_GAP:
                self._total += (self._last_power + power) / 2 * dt / 3600 / 1000
        self._last_power, self._last_time = power, now

    @property
    def native_value(self) -> float:
        return round(self._total, 5)


class MyLightEnergySensor(_Integrator, MyLightEntity, RestoreSensor):
    """Énergie cumulée (kWh) d'un équipement.

    sign=+1 : énergie consommée/importée (puissance > 0)
    sign=-1 : énergie injectée/exportée (puissance < 0, compteur signé)
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(
        self, coordinator: MyLightCoordinator, key: str, energy_key: str, sign: int
    ) -> None:
        super().__init__(coordinator, key)
        self._sign = sign
        self._attr_translation_key = energy_key
        self._attr_unique_id = f"{key}_{energy_key}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._restore_total()

    @callback
    def _handle_coordinator_update(self) -> None:
        device = self.device
        power = device.total_power if device else None
        if not self.available or power is None:
            self._integrate(None)
        else:
            self._integrate(max(power * self._sign, 0.0))
        super()._handle_coordinator_update()


# --------------------------------------------------------------------------
# Capteurs « installation » : production, réseau, consommation de la maison
# --------------------------------------------------------------------------


def _site_values(
    coordinator: MyLightCoordinator, prod_key: str
) -> tuple[float | None, float | None]:
    """(production W ≥ 0, réseau W signé) ; None si non disponible."""
    data = coordinator.data
    prod = data.get(prod_key)
    grid = next((d for d in data.values() if d.device_type == "GMD"), None)

    def usable(d: MyLightDevice | None) -> bool:
        return (
            d is not None
            and d.total_power is not None
            and d.status not in UNAVAILABLE_STATUSES
        )

    production = max(prod.total_power, 0.0) if usable(prod) else None
    grid_power = grid.total_power if usable(grid) else None
    return production, grid_power


def _house(production: float | None, grid: float | None) -> float | None:
    """Consommation = production + réseau (réseau>0 : soutirage, <0 : injection)."""
    if production is None or grid is None:
        return None
    return max(production + grid, 0.0)


SITE_POWER = {
    "production_power": lambda p, g: p,
    "grid_power": lambda p, g: g,
    "house_power": _house,
}
SITE_ENERGY = {
    "production_energy": lambda p, g: p,
    "house_energy": _house,
}


class MyLightSitePowerSensor(MyLightSiteEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, entry_id: str, prod_key: str, kind: str) -> None:
        super().__init__(coordinator, entry_id)
        self._prod_key, self._kind = prod_key, kind
        self._attr_translation_key = kind
        self._attr_unique_id = f"{entry_id}_{kind}"

    @property
    def native_value(self) -> float | None:
        p, g = _site_values(self.coordinator, self._prod_key)
        value = SITE_POWER[self._kind](p, g)
        return None if value is None else round(value, 1)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None


class MyLightSiteEnergySensor(_Integrator, MyLightSiteEntity, RestoreSensor):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, entry_id: str, prod_key: str, kind: str) -> None:
        super().__init__(coordinator, entry_id)
        self._prod_key, self._kind = prod_key, kind
        self._attr_translation_key = kind
        self._attr_unique_id = f"{entry_id}_{kind}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._restore_total()

    @callback
    def _handle_coordinator_update(self) -> None:
        p, g = _site_values(self.coordinator, self._prod_key)
        self._integrate(SITE_ENERGY[self._kind](p, g))
        super()._handle_coordinator_update()

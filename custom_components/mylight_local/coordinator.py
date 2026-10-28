"""Coordinateur de mise à jour."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    MyLightAuthError,
    MyLightConnectionError,
    MyLightDevice,
    MyLightError,
    MyLightLocalApi,
)
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type MyLightConfigEntry = ConfigEntry[MyLightCoordinator]


class MyLightCoordinator(DataUpdateCoordinator[dict[str, MyLightDevice]]):
    """Interroge la passerelle et distribue les données."""

    config_entry: MyLightConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: MyLightConfigEntry, api: MyLightLocalApi
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, MyLightDevice]:
        try:
            devices = await self.api.get_devices()
        except MyLightAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (MyLightConnectionError, MyLightError) as err:
            raise UpdateFailed(f"Erreur de communication: {err}") from err
        return {d.key: d for d in devices}

    async def async_set_state(self, device: MyLightDevice, state: bool) -> None:
        """Allume/éteint une prise puis rafraîchit."""
        try:
            await self.api.set_device_state(device.key, state)
        except MyLightError as err:
            raise HomeAssistantError(f"Commande refusée: {err}") from err
        # Mise à jour optimiste, puis confirmation par la passerelle.
        device.state = state
        self.async_update_listeners()
        await asyncio.sleep(2)
        await self.async_request_refresh()

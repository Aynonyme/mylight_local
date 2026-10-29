"""Configuration par l'interface."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    MyLightAuthError,
    MyLightConnectionError,
    MyLightError,
    MyLightLocalApi,
)
from .const import (
    CONF_PRODUCTION_DEVICE,
    CONF_SCAN_INTERVAL,
    DEVICE_LABELS,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


def _clean_host(host: str) -> str:
    return host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")


class MyLightConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = _clean_host(user_input[CONF_HOST])
            api = MyLightLocalApi(
                async_get_clientsession(self.hass),
                host,
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
            )
            try:
                devices = await api.get_devices()
            except MyLightAuthError:
                errors["base"] = "invalid_auth"
            except MyLightConnectionError:
                errors["base"] = "cannot_connect"
            except MyLightError:
                errors["base"] = "unknown"
            else:
                master = next((d for d in devices if d.device_type == "MST"), None)
                await self.async_set_unique_id(master.key if master else host)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                data = {CONF_HOST: host}
                if user_input.get(CONF_USERNAME):
                    data[CONF_USERNAME] = user_input[CONF_USERNAME]
                    data[CONF_PASSWORD] = user_input.get(CONF_PASSWORD, "")
                return self.async_create_entry(title=f"MyLight ({host})", data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
                vol.Optional(
                    CONF_USERNAME,
                    description={
                        "suggested_value": (user_input or {}).get(
                            CONF_USERNAME, DEFAULT_USERNAME
                        )
                    },
                ): str,
                vol.Optional(
                    CONF_PASSWORD,
                    description={
                        "suggested_value": (user_input or {}).get(
                            CONF_PASSWORD, DEFAULT_PASSWORD
                        )
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api = MyLightLocalApi(
                async_get_clientsession(self.hass),
                entry.data[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await api.get_devices()
            except MyLightAuthError:
                errors["base"] = "invalid_auth"
            except MyLightConnectionError:
                errors["base"] = "cannot_connect"
            except MyLightError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
                ): str,
                vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return MyLightOptionsFlow()


class MyLightOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        current = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        # Appareils pouvant représenter la production (tout sauf compteur réseau / master).
        coordinator = getattr(self.config_entry, "runtime_data", None)
        candidates = []
        if coordinator is not None and coordinator.data:
            for key, dev in coordinator.data.items():
                if dev.device_type in ("GMD", "MST") or dev.total_power is None:
                    continue
                label = DEVICE_LABELS.get(dev.device_type, dev.device_type)
                candidates.append(SelectOptionDict(value=key, label=f"{label} {key[-4:]} ({key})"))

        prod_field = vol.Optional(
            CONF_PRODUCTION_DEVICE,
            description={"suggested_value": options.get(CONF_PRODUCTION_DEVICE)},
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
                prod_field: SelectSelector(
                    SelectSelectorConfig(options=candidates, mode=SelectSelectorMode.DROPDOWN)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

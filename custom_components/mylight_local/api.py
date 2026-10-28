"""Client JSON-RPC pour la passerelle locale MyLight (SmartPlug Master).

Protocole déduit du JavaScript de l'interface web embarquée (firmware 1.5.3) :
  POST http://<ip>/rpc   {"method": "getDevices"}
  POST http://<ip>/rpc   {"method": "setDeviceState", "parameters": {"mac": "...", "state": true}}
Ce module n'a volontairement aucune dépendance à Home Assistant.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import aiohttp

RPC_PATH = "/rpc"
REQUEST_TIMEOUT = 10


class MyLightError(Exception):
    """Erreur générique."""


class MyLightConnectionError(MyLightError):
    """Passerelle injoignable."""


class MyLightAuthError(MyLightError):
    """Authentification refusée (HTTP 401)."""


class MyLightApiError(MyLightError):
    """Réponse inattendue ou erreur renvoyée par la passerelle."""


@dataclass
class MyLightDevice:
    """Un équipement vu par la passerelle."""

    device_type: str
    eth_mac: str | None
    plc_mac: str | None
    status: str
    firmware: str | None
    power: float | None  # appareils monophasés
    phases: tuple[float, float, float] | None  # appareils triphasés
    state: bool | None  # None pour les appareils non commandables
    embedded: bool

    @property
    def key(self) -> str:
        """Identifiant stable, identique au MAC utilisé par l'interface web pour commander."""
        if self.device_type in ("ETH", "MST") and self.eth_mac:
            return self.eth_mac
        return self.plc_mac or self.eth_mac or ""

    @property
    def total_power(self) -> float | None:
        """Puissance totale en W."""
        if self.phases is not None:
            return round(sum(self.phases), 1)
        return self.power

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> MyLightDevice:
        phases = None
        if all(raw.get(k) is not None for k in ("power1", "power2", "power3")):
            phases = (float(raw["power1"]), float(raw["power2"]), float(raw["power3"]))
        power = None
        if phases is None and raw.get("power") is not None:
            power = float(raw["power"])
        state = raw.get("state")
        firmware = raw.get("firmware")
        return cls(
            device_type=str(raw.get("deviceType", "")).upper(),
            eth_mac=raw.get("ethMac") or None,
            plc_mac=raw.get("plcMac") or None,
            status=str(raw.get("status", "unknown")),
            firmware=str(firmware) if firmware is not None else None,
            power=power,
            phases=phases,
            state=bool(state) if state is not None else None,
            embedded=bool(raw.get("embedded", False)),
        )


class MyLightLocalApi:
    """Client asynchrone de la passerelle."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._url = f"http://{host}{RPC_PATH}"
        self._auth = (
            aiohttp.BasicAuth(username, password or "") if username else None
        )

    async def _rpc(self, method: str, parameters: dict[str, Any] | None = None) -> Any:
        payload: dict[str, Any] = {"method": method}
        if parameters is not None:
            payload["parameters"] = parameters
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.post(
                    self._url, json=payload, auth=self._auth
                ) as resp:
                    if resp.status == 401:
                        raise MyLightAuthError("Authentification refusée")
                    resp.raise_for_status()
                    text = await resp.text()
        except MyLightError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MyLightConnectionError(str(err) or type(err).__name__) from err

        try:
            data = json.loads(text)
        except ValueError as err:
            raise MyLightApiError(f"Réponse non JSON: {text[:100]!r}") from err
        if isinstance(data, dict) and data.get("error"):
            raise MyLightApiError(f"Erreur de la passerelle: {data['error']}")
        return data

    async def get_devices(self) -> list[MyLightDevice]:
        data = await self._rpc("getDevices")
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, list):
            raise MyLightApiError(f"Format getDevices inattendu: {str(data)[:100]}")
        devices = []
        for raw in result:
            if not isinstance(raw, dict):
                continue
            device = MyLightDevice.from_json(raw)
            if device.key:
                devices.append(device)
        return devices

    async def set_device_state(self, mac: str, state: bool) -> None:
        await self._rpc("setDeviceState", {"mac": mac, "state": state})

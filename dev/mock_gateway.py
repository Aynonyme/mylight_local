"""Fausse passerelle MyLight (POST /rpc) pour tester l'intégration sans matériel.

Reproduit le comportement déduit de l'interface web 1.5.3 : getDevices /
setDeviceState, avec une puissance qui fluctue et un état ON/OFF mémorisé.
Tapez 'offline'/'online' n'est pas géré ici : modifiez DEVICES pour d'autres cas.
"""
import random

from aiohttp import web

DEVICES = [
    {"ethMac": "0013C139EEAB", "plcMac": "0013C139EFA5", "deviceType": "MST",
     "status": "online", "power": 130.0, "firmware": "2.06/2.87"},
    {"plcMac": "0013C13A3B8A", "deviceType": "TPH", "status": "unpaired",
     "power1": 0.0, "power2": 0.0, "power3": 0.0, "firmware": "9.14", "state": True},
    {"ethMac": "0013C139F08D", "plcMac": "0013C139F187", "deviceType": "ETH",
     "status": "online", "power": 510.0, "firmware": "2.06/1.95", "state": True},
    {"plcMac": "0013C13A3AC2", "deviceType": "TPH", "status": "online",
     "power1": 0.0, "power2": 0.0, "power3": 0.0, "firmware": "9.14", "state": True},
    {"plcMac": "0013C139F239", "deviceType": "SW", "status": "online",
     "power": 46.0, "firmware": "7.11", "state": True},
    {"plcMac": "0013C139F27C", "deviceType": "SW", "status": "online",
     "power": 26.0, "firmware": "7.11", "state": True},
    {"plcMac": "0013C139F705", "deviceType": "GMD", "status": "online",
     "power1": 92.0, "power2": 600.0, "power3": 567.0, "firmware": "7.18"},
]
BASE = {id(d): {k: v for k, v in d.items() if k.startswith("power")} for d in DEVICES}


def control_mac(d):
    return d.get("ethMac") if d["deviceType"] in ("ETH", "MST") else d.get("plcMac")


def snapshot():
    out = []
    for d in DEVICES:
        item = dict(d)
        for k, base in BASE[id(d)].items():
            off = d.get("state") is False
            item[k] = 0.0 if off else round(max(base * random.uniform(0.95, 1.05), 0), 1)
        out.append(item)
    return out


async def rpc(request):
    body = await request.json()
    method, params = body.get("method"), body.get("parameters") or {}
    print("RPC", body, flush=True)
    if method == "getDevices":
        return web.json_response({"result": snapshot()})
    if method == "setDeviceState":
        for d in DEVICES:
            if control_mac(d) == params.get("mac") and "state" in d:
                d["state"] = bool(params["state"])
                return web.json_response({"result": "ok"})
        return web.json_response({"error": "unknown mac"})
    if method == "getServerUrl":
        return web.json_response({"result": {"url": "https://mock.invalid:7001"}})
    return web.json_response({"error": f"unknown method {method}"})


app = web.Application()
app.router.add_post("/rpc", rpc)
web.run_app(app, port=8099)

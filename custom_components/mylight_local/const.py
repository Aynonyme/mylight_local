"""Constantes de l'intégration MyLight Systems (local)."""
from __future__ import annotations

DOMAIN = "mylight_local"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 10  # secondes (la page web officielle rafraîchit toutes les 10 s)
DEFAULT_USERNAME = "admin"  # identifiants d'usine de la SmartPlug Master
DEFAULT_PASSWORD = "welcome"
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 300

MANUFACTURER = "MyLight Systems"

DEVICE_LABELS: dict[str, str] = {
    "MST": "SmartPlug Master (rouge)",
    "ETH": "SmartPlug Ethernet (bleue)",
    "SW": "SmartPlug Control (blanche)",
    "TPH": "SmartPlug triphasée",
    "GMD": "Compteur général",
    "BAT": "Batterie",
}

# Mêmes règles que l'interface web : pas de bouton ON/OFF pour ces types.
NON_CONTROLLABLE_TYPES = {"GMD", "MST", "BAT"}

# Statuts pour lesquels la commande est désactivée dans l'interface web.
UNAVAILABLE_STATUSES = {"offline", "upgrading"}

CONF_PRODUCTION_DEVICE = "production_device"

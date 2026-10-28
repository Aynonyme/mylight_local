<p align="center"><img src="images/logo.png" alt="MyLight Systems" width="250"></p>

# MyLight Systems (local) pour Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Validate](https://github.com/Aynonyme/mylight_local/actions/workflows/validate.yml/badge.svg)](https://github.com/Aynonyme/mylight_local/actions/workflows/validate.yml)

Intégration **100 % locale** : elle interroge l'interface web de la SmartPlug Master (prise rouge, firmware 1.5.3) via son API JSON-RPC `/rpc`, sans passer par le cloud MyLight.

> Projet communautaire, **non affilié à MyLight Systems**. Le logo appartient à MyLight Systems. Développé à partir de l'interface web de la passerelle, sans documentation officielle : testé uniquement sur le firmware 1.5.3.

## Installation

**HACS** : HACS → ⋮ → *Dépôts personnalisés* → `https://github.com/Aynonyme/mylight_local`, catégorie *Intégration* → installer → redémarrer Home Assistant.

**Manuelle** : copier `custom_components/mylight_local` dans `config/custom_components/`, puis redémarrer.

Ensuite : Paramètres → Appareils et services → Ajouter une intégration → **MyLight Systems (local)** → saisir l'adresse IP de la prise rouge (celle de son interface web). Réservez-lui une IP fixe dans votre box.

## Entités (créées automatiquement pour chaque équipement)

| Type | Équipement | Entités |
|---|---|---|
| MST | SmartPlug Master (rouge) | puissance, énergie, statut |
| ETH | SmartPlug Ethernet (bleue) | puissance, énergie, statut, **interrupteur** |
| SW | SmartPlug Control (blanche) | puissance, énergie, statut, **interrupteur** |
| TPH | prise triphasée | puissance totale + P1/P2/P3, énergie, statut, **interrupteur** |
| GMD | compteur réseau triphasé | puissance totale + P1/P2/P3, énergie importée, énergie exportée, statut |

- La passerelle ne fournit que des watts : les **kWh sont calculés par intégration** (compatibles tableau de bord Énergie, conservés après redémarrage, rien n'est cumulé pendant une coupure de communication). Ils peuvent différer légèrement de votre compteur.
- Un appareil hors ligne est indisponible ; le capteur « Statut » reste visible.
- Intervalle d'interrogation réglable (défaut 10 s) dans les options.

## Production solaire et consommation de la maison

La passerelle n'expose pas de « production » en tant que telle : un compteur/prise triphasé (TPH) la mesure, et le GMD est le compteur réseau signé (positif = soutirage, négatif = injection). Dans **Configurer** (options de l'intégration), choisissez l'**appareil de production solaire** ; une entrée « Installation MyLight » apparaît avec :

- Production solaire (W) et Énergie produite (kWh)
- Puissance réseau (W, signée)
- Consommation maison (W) = production + réseau, et Énergie consommée maison (kWh)

Tableau de bord Énergie : **Réseau** → consommation = *Énergie importée* du GMD, retour = *Énergie exportée* du GMD ; **Panneaux solaires** → *Énergie produite* de l'installation.

## Licence

MIT, voir [LICENSE](LICENSE).

"""Charge et sauvegarde la configuration Indoor/Flint depuis des fichiers
TOML lisibles par un humain, pour qu'un bénévole du club puisse ajuster les
temps, distances et images de cible sans toucher au code Python.

Lecture : ``tomllib``, dans la bibliothèque standard depuis Python 3.11 --
aucune dépendance externe, ce qui compte pour la compatibilité Pydroid.
Écriture : TOML n'a pas de support d'écriture en stdlib ; plutôt que
d'ajouter une dépendance tierce pour ça, on utilise un petit sérialiseur
maison, largement suffisant pour les types simples qu'on manipule ici
(chaînes, nombres, booléens, listes de chaînes).
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import fields
from pathlib import Path
from typing import Any

from fletchtime.engine import FlintConfig, IndoorConfig

# FletchTime opère sur le répertoire courant, comme la plupart des outils en
# ligne de commande (jekyll, hugo...) : `config/` vit à côté d'où la
# commande est lancée -- que ce soit un clone du dépôt (le dev lance
# généralement les commandes depuis la racine) ou un `pip install
# fletchtime` lancé depuis le dossier de travail du club. Empaqueté par
# PyInstaller, on repart de l'exécutable lui-même à la place (voir
# fletchtime/__main__.py, même logique).
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path.cwd()
CONFIG_DIR = PROJECT_ROOT / "config"
INDOOR_TOML = CONFIG_DIR / "indoor.toml"
FLINT_TOML = CONFIG_DIR / "flint.toml"
APP_TOML = CONFIG_DIR / "app.toml"
# Fichier séparé de app.toml exprès : il contient un vrai secret (le mot de
# passe), jamais versionné (voir .gitignore) -- contrairement à app.toml,
# indoor.toml, flint.toml qui sont des réglages partageables sans risque.
AUTH_TOML = CONFIG_DIR / "auth.toml"

APP_COMMENTS: dict[str, str] = {
    "sound_pack": "Nom du dossier dans web/assets/sounds/packs/ à utiliser (ex. classic)",
    "countdown_tick_seconds": "Nombre de secondes avant la fin d'un décompte où countdown_tick est émis (0 = désactivé)",
}
DEFAULT_APP_CONFIG: dict[str, Any] = {"sound_pack": "classic", "countdown_tick_seconds": 5}

AUTH_COMMENTS: dict[str, str] = {
    "password": (
        "Mot de passe requis pour piloter le match et modifier la "
        "configuration -- vide = aucune protection (comportement actuel)"
    ),
}
DEFAULT_AUTH_CONFIG: dict[str, Any] = {"password": ""}

INDOOR_COMMENTS: dict[str, str] = {
    "series": "Nombre de séries",
    "ends_per_series": "Nombre de volées par série",
    "arrows_per_end": "Nombre de flèches par volée",
    "prep_time": "Temps de mise en place avant chaque volée (secondes)",
    "shoot_time": "Temps de tir total, décompte continu (secondes)",
    "orange_warning_time": "Passage à l'orange quand il reste ce temps (secondes)",
    "distance_label": "Distance affichée à l'écran",
    "target_image_recurve": "Image du blason recourbe/trad (chemin relatif à web/)",
    "target_image_compound": "Image du blason poulies (chemin relatif à web/)",
    "turn_mode": "Ordre des relais par défaut : ab_then_cd, cd_then_ab, ab_only, cd_only",
    "alternate_relay_order_each_series": "Alterner l'ordre des relais à chaque série (true/false)",
}

FLINT_COMMENTS: dict[str, str] = {
    "units": "Nombre d'unités standards (2 = un parcours complet)",
    "standard_ends_per_unit": "Nombre de volées standards par unité",
    "arrows_per_standard_end": "Nombre de flèches par volée standard",
    "standard_prep_time": "Mise en place avant chaque volée standard (secondes)",
    "standard_shoot_time": "Temps de tir d'une volée standard (secondes)",
    "standard_orange_warning_time": "Seuil orange volée standard (secondes)",
    "standard_distances": "Les 6 distances des volées standards, dans l'ordre",
    "standard_target_image_1spot": "Blason 1 spot (volées impaires)",
    "standard_target_image_4spot": "Blason 4 spots (volées paires)",
    "walkup_arrows": "Nombre de flèches du walk-up",
    "walkup_time_per_arrow": "Temps de tir par flèche du walk-up (secondes)",
    "walkup_prep_time": "Mise en place avant chaque flèche du walk-up (secondes)",
    "walkup_orange_warning_time": "Seuil orange par flèche du walk-up (secondes)",
    "walkup_distances": "Les 4 distances du walk-up, dans l'ordre",
    "walkup_target_image": "Blason du walk-up",
    "turn_mode": "Ordre des relais par défaut",
    "alternate_relay_order_each_unit": "Alterner l'ordre des relais à chaque unité",
}


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _filtered_overrides(data: dict[str, Any], config_cls: type) -> dict[str, Any]:
    """Ignore silently any key in the file that isn't a real field -- a
    typo or leftover key in a hand-edited TOML file shouldn't crash the
    server, just be ignored."""
    valid_names = {f.name for f in fields(config_cls)}
    return {k: v for k, v in data.items() if k in valid_names}


def load_indoor_config() -> IndoorConfig:
    """Reads config/indoor.toml, falling back to IndoorConfig's own
    defaults for any missing file or missing field."""
    data = _filtered_overrides(_load_toml(INDOOR_TOML), IndoorConfig)
    return IndoorConfig(**data)


def load_flint_config() -> FlintConfig:
    """Reads config/flint.toml, falling back to FlintConfig's own
    defaults for any missing file or missing field."""
    data = _filtered_overrides(_load_toml(FLINT_TOML), FlintConfig)
    return FlintConfig(**data)


def load_app_config() -> dict[str, Any]:
    """App-wide settings that aren't specific to Indoor or Flint (currently
    just the active sound pack). Not a dataclass -- there's only one field
    today and it may grow, so a plain dict merged over sensible defaults is
    simpler than a formal schema for now."""
    data = _load_toml(APP_TOML)
    merged = dict(DEFAULT_APP_CONFIG)
    merged.update({k: v for k, v in data.items() if k in DEFAULT_APP_CONFIG})
    return merged


def save_app_config(overrides: dict[str, Any]) -> dict[str, Any]:
    merged = load_app_config()
    merged.update({k: v for k, v in overrides.items() if k in DEFAULT_APP_CONFIG})
    if merged["countdown_tick_seconds"] < 0:
        raise ValueError(
            "countdown_tick_seconds must be >= 0, got " f"{merged['countdown_tick_seconds']}"
        )
    _write_toml(APP_TOML, merged, APP_COMMENTS)
    return merged


def load_auth_config() -> dict[str, Any]:
    data = _load_toml(AUTH_TOML)
    merged = dict(DEFAULT_AUTH_CONFIG)
    merged.update({k: v for k, v in data.items() if k in DEFAULT_AUTH_CONFIG})
    merged["password"] = str(merged["password"])
    return merged


def save_auth_config(overrides: dict[str, Any]) -> dict[str, Any]:
    merged = load_auth_config()
    merged.update({k: v for k, v in overrides.items() if k in DEFAULT_AUTH_CONFIG})
    merged["password"] = str(merged["password"])
    _write_toml(AUTH_TOML, merged, AUTH_COMMENTS)
    return merged


def save_indoor_config(overrides: dict[str, Any]) -> IndoorConfig:
    """Validates ``overrides`` by constructing a real IndoorConfig (raises
    ValueError if inconsistent, e.g. orange_warning_time > shoot_time)
    before writing anything to disk."""
    filtered = _filtered_overrides(overrides, IndoorConfig)
    config = IndoorConfig(**filtered)
    values = {f.name: getattr(config, f.name) for f in fields(IndoorConfig)}
    _write_toml(INDOOR_TOML, values, INDOOR_COMMENTS)
    return config


def save_flint_config(overrides: dict[str, Any]) -> FlintConfig:
    """Validates ``overrides`` by constructing a real FlintConfig (raises
    ValueError if inconsistent) before writing anything to disk."""
    filtered = _filtered_overrides(overrides, FlintConfig)
    config = FlintConfig(**filtered)
    values = {f.name: getattr(config, f.name) for f in fields(FlintConfig)}
    _write_toml(FLINT_TOML, values, FLINT_COMMENTS)
    return config


# -- petit sérialiseur TOML maison (écriture uniquement) ----------------------


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def _write_toml(path: Path, values: dict[str, Any], comments: dict[str, str]) -> None:
    lines = []
    for key, value in values.items():
        comment = comments.get(key)
        if comment:
            lines.append(f"# {comment}")
        lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

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

import json
import logging
import re
import sys
import time
import tomllib
from dataclasses import fields
from pathlib import Path
from typing import Any

from fletchtime.engine import FlintConfig, IndoorConfig

logger = logging.getLogger("fletchtime.server")

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
# Instantané du match en cours (JSON, pas TOML : structure imbriquée,
# jamais éditée à la main par un humain contrairement aux fichiers
# ci-dessus) -- permet de reprendre après un plantage/redémarrage du
# serveur plutôt que de perdre la progression en cours. Jamais versionné
# (voir .gitignore) : propre à une session de match en cours, pas un
# réglage du club.
MATCH_STATE_JSON = CONFIG_DIR / "match_state.json"
# Préférences de la fenêtre graphique (thème...) -- fichier séparé de
# app.toml exprès : ce ne sont pas des réglages du match/serveur diffusés
# aux écrans web, juste des préférences purement locales à qui lance la
# fenêtre sur cette machine précise.
GUI_TOML = CONFIG_DIR / "gui.toml"

APP_COMMENTS: dict[str, str] = {
    "sound_pack": "Nom du dossier dans web/assets/sounds/packs/ à utiliser (ex. classic)",
    "countdown_tick_seconds": "Nombre de secondes avant la fin d'un décompte où countdown_tick est émis (0 = désactivé)",
    "color_red": "Couleur de fond de l'écran en phase rouge (préparation), format #rrggbb",
    "color_orange": "Couleur de fond de l'écran en phase orange (fin de tir proche), format #rrggbb",
    "color_green": "Couleur de fond de l'écran en phase verte (tir), format #rrggbb",
    "color_pause": "Couleur de fond de l'écran en pause (récupération des flèches), format #rrggbb",
    "color_emergency": "Couleur de fond de l'écran en urgence (clignote), format #rrggbb",
}
DEFAULT_APP_CONFIG: dict[str, Any] = {
    "sound_pack": "classic",
    "countdown_tick_seconds": 5,
    # Mêmes valeurs que les couleurs auparavant figées dans le CSS de
    # display.html -- rien ne change visuellement tant que personne ne
    # les personnalise depuis la page de configuration.
    "color_red": "#7f1d1d",
    "color_orange": "#b45309",
    "color_green": "#14532d",
    "color_pause": "#374151",
    "color_emergency": "#dc2626",
}

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

GUI_COMMENTS: dict[str, str] = {
    "theme": 'Thème de la fenêtre : "system" (suit le thème du système), "light" ou "dark"',
    "http_port": "Port HTTP (pages web) -- change ceci pour faire tourner plusieurs salles sur le même PC",
    "ws_port": "Port WebSocket (temps réel) -- doit être différent du port HTTP",
}
DEFAULT_GUI_CONFIG: dict[str, Any] = {"theme": "system", "http_port": 8000, "ws_port": 8765}

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
    for key in ("color_red", "color_orange", "color_green", "color_pause", "color_emergency"):
        if not _HEX_COLOR_RE.match(merged[key]):
            raise ValueError(f"{key} must be a #rrggbb hex color, got {merged[key]!r}")
    _write_toml(APP_TOML, merged, APP_COMMENTS)
    return merged


def load_gui_config() -> dict[str, Any]:
    """Préférences de la fenêtre graphique -- voir GUI_TOML. Comme
    load_app_config, un plain dict plutôt qu'une dataclass formelle : un
    seul champ aujourd'hui, peut grandir."""
    data = _load_toml(GUI_TOML)
    merged = dict(DEFAULT_GUI_CONFIG)
    merged.update({k: v for k, v in data.items() if k in DEFAULT_GUI_CONFIG})
    return merged


def save_gui_config(overrides: dict[str, Any]) -> dict[str, Any]:
    merged = load_gui_config()
    merged.update({k: v for k, v in overrides.items() if k in DEFAULT_GUI_CONFIG})
    if merged["theme"] not in ("system", "light", "dark"):
        raise ValueError(f'theme must be "system", "light" or "dark", got {merged["theme"]!r}')
    for key in ("http_port", "ws_port"):
        port = merged[key]
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise ValueError(f"{key} must be an integer between 1 and 65535, got {port!r}")
    if merged["http_port"] == merged["ws_port"]:
        raise ValueError("http_port and ws_port must be different")
    _write_toml(GUI_TOML, merged, GUI_COMMENTS)
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


# -- instantané du match en cours (récupération après crash) ----------------


def save_match_snapshot(data: dict[str, Any]) -> None:
    """Écriture atomique (fichier temporaire puis renommage) : ne laisse
    jamais un fichier à moitié écrit si le processus s'arrête précisément
    pendant l'écriture -- ``Path.replace`` est garanti atomique aussi bien
    sous Linux/macOS que Windows depuis Python 3.3+.

    Ceci dit, "atomique" ne veut pas dire "ne peut jamais échouer" : sous
    Windows, remplacer un fichier peut lever une erreur de "violation de
    partage" si un autre processus l'a ouvert au même instant (antivirus,
    surveillance de fichiers d'un IDE, Git Bash...) -- constaté en
    pratique (voir docs/architecture.md, section sur la résilience de la
    boucle de décompte, appelante de cette fonction à chaque tick).
    Ce verrou est transitoire par nature, d'où quelques tentatives avant
    d'abandonner. Échoue silencieusement (juste un avertissement dans le
    journal) plutôt que de lever : un instantané manqué n'est jamais
    grave (le prochain tick, ~200ms plus tard, retente), alors qu'une
    exception qui remonterait perturberait aussi la diffusion de l'état
    aux écrans pour ce même tick, pour une raison qui n'a rien à voir
    avec eux."""
    MATCH_STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = MATCH_STATE_JSON.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        logger.warning("Échec d'écriture de l'instantané de match (fichier temporaire)")
        return

    last_error: OSError | None = None
    for attempt in range(3):
        try:
            tmp_path.replace(MATCH_STATE_JSON)
            return
        except OSError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.05)
    logger.warning(
        "Échec de sauvegarde de l'instantané de match après plusieurs tentatives "
        "(fichier probablement verrouillé par un autre processus, ex. antivirus, "
        "IDE) : %s",
        last_error,
    )


def load_match_snapshot() -> dict[str, Any] | None:
    """``None`` si aucun instantané n'existe, ou s'il est corrompu/
    illisible -- une reprise ratée doit se rabattre silencieusement sur un
    démarrage normal, jamais faire planter le serveur au lancement."""
    if not MATCH_STATE_JSON.is_file():
        return None
    try:
        return json.loads(MATCH_STATE_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def clear_match_snapshot() -> None:
    MATCH_STATE_JSON.unlink(missing_ok=True)

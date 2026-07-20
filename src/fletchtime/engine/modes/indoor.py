"""Indoor round: fixed number of series, each made of several ends of a
fixed number of arrows, all shot at a single distance. Matches the club's
concours format ("2 séries de 6 volées de 5 flèches") but every number is
configurable.

A-B / C-D are *relays within the same volée*, not separate ends: when a
target is shared, one pair shoots first, then the other -- the volée
number does not change between them, only once *all* configured relays for
that end have shot does the engine move to the next volée. Whether a match
uses both relays (and in which order) or just one is a per-match setting
(``turn_mode``), fixed before the match starts and never toggled mid-match.

The club's actual competition alternates which relay leads from one series
to the next (série 1 : A-B puis C-D -- série 2 : C-D puis A-B) -- this is
``alternate_relay_order_each_series``, on by default.

Séries et volées are tracked as separate numbers on every step, matching
FlintMode's model: ``unit_number`` is the série (1, 2, ...) and
``end_number``/``total_ends`` are the volée *within that série* (e.g. 1-6),
not a running total across the whole match.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Phase
from ..sequence import Step
from ..turn_modes import TURN_MODES
from .base import ShootingMode


@dataclass
class IndoorConfig:
    series: int = 2
    ends_per_series: int = 6
    arrows_per_end: int = 5

    prep_time: float = 10.0  # red: préparation / mise en place
    shoot_time: float = 240.0  # temps de tir total, continu (règle IFAA : 4 min)
    orange_warning_time: float = 30.0  # passage à l'orange quand il reste ce temps (sans reset)

    distance_label: str = "20 yards"
    # Deux blasons affichés côte à côte : recourbe/trad à gauche, poulies à
    # droite -- les deux catégories tirent souvent ensemble en Indoor.
    target_image_recurve: str = "assets/targets/indoor_recurve.svg"
    target_image_compound: str = "assets/targets/indoor_compound.svg"

    # Comment les archers se relaient sur un même blason pendant une volée :
    # "ab_then_cd", "cd_then_ab" (les deux relais, dans un ordre ou
    # l'autre), "ab_only" ou "cd_only" (un seul relais). Ceci fixe l'ordre
    # de la *première* série ; fixé avant le match, ne change jamais en
    # cours de concours.
    turn_mode: str = "ab_then_cd"

    # Le concours du club alterne l'ordre des relais d'une série à l'autre
    # (série 1 : A-B puis C-D -- série 2 : C-D puis A-B). Sans effet sur
    # "ab_only"/"cd_only" (un seul relais, rien à inverser).
    alternate_relay_order_each_series: bool = True

    def __post_init__(self) -> None:
        if self.series < 1 or self.ends_per_series < 1 or self.arrows_per_end < 1:
            raise ValueError("series, ends_per_series and arrows_per_end must be >= 1")
        for name, value in (
            ("prep_time", self.prep_time),
            ("shoot_time", self.shoot_time),
            ("orange_warning_time", self.orange_warning_time),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        if self.orange_warning_time > self.shoot_time:
            raise ValueError(
                "orange_warning_time must be <= shoot_time, got "
                f"orange_warning_time={self.orange_warning_time} > shoot_time={self.shoot_time}"
            )
        if self.turn_mode not in TURN_MODES:
            raise ValueError(
                f"turn_mode must be one of {sorted(TURN_MODES)}, got {self.turn_mode!r}"
            )


class IndoorMode(ShootingMode):
    def __init__(self, config: IndoorConfig | None = None) -> None:
        self.config = config or IndoorConfig()

    def _series_index(self, global_end_index: int) -> int:
        return (global_end_index - 1) // self.config.ends_per_series + 1

    def _end_in_series(self, global_end_index: int) -> int:
        return (global_end_index - 1) % self.config.ends_per_series + 1

    def _relays_for(self, global_end_index: int) -> list[str]:
        cfg = self.config
        base = TURN_MODES[cfg.turn_mode]
        series_index = self._series_index(global_end_index)
        if cfg.alternate_relay_order_each_series and len(base) == 2 and series_index % 2 == 0:
            return list(reversed(base))
        return base

    def build_sequence(self) -> list[Step]:
        cfg = self.config
        total_global_ends = cfg.series * cfg.ends_per_series

        def relay_block(global_end_index: int, turn: str) -> list[Step]:
            common = dict(
                current_turn=turn,
                end_number=self._end_in_series(global_end_index),
                total_ends=cfg.ends_per_series,
                unit_number=self._series_index(global_end_index),
                distance_label=cfg.distance_label,
                target_image=cfg.target_image_recurve,
                target_image_2=cfg.target_image_compound,
            )
            block: list[Step] = []
            if cfg.prep_time > 0:
                block.append(
                    Step(
                        phase=Phase.RED, duration=cfg.prep_time, sound_event="prep_start", **common
                    )
                )
            block.append(
                Step(
                    phase=Phase.GREEN,
                    duration=cfg.shoot_time,
                    sound_event="shoot_start",
                    orange_threshold=(
                        cfg.orange_warning_time if cfg.orange_warning_time > 0 else None
                    ),
                    orange_sound_event="warning_orange",
                    **common,
                )
            )
            return block

        steps: list[Step] = []
        for global_end_index in range(1, total_global_ends + 1):
            for turn in self._relays_for(global_end_index):
                # Le relais suivant (s'il y en a un) commence par son propre
                # RED de préparation -- pas besoin de PAUSE entre les deux
                # relais, ce n'est pas une récupération de flèches, juste un
                # changement de tireurs sur la ligne.
                steps.extend(relay_block(global_end_index, turn))

            has_next_end = global_end_index < total_global_ends
            if has_next_end:
                # Fin de volée (tous les relais ont tiré) : récupération
                # des flèches, pas de décompte. Le DOS déclenche la volée
                # suivante manuellement (next()). La distance affichée
                # pendant le ramassage est déjà celle de la volée suivante.
                next_index = global_end_index + 1
                next_relays = self._relays_for(next_index)
                steps.append(
                    Step(
                        phase=Phase.PAUSE,
                        duration=None,
                        current_turn=next_relays[0],
                        end_number=self._end_in_series(next_index),
                        total_ends=cfg.ends_per_series,
                        unit_number=self._series_index(next_index),
                        distance_label=cfg.distance_label,
                        target_image=cfg.target_image_recurve,
                        target_image_2=cfg.target_image_compound,
                    )
                )
        return steps

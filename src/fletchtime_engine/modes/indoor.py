"""Indoor round: fixed number of series, each made of several ends of a
fixed number of arrows, all shot at a single distance. Matches the club's
concours format ("2 séries de 6 volées de 5 flèches") but every number is
configurable.

A-B / C-D are *relays within the same volée*, not separate ends: when a
target is shared, one pair shoots first (A-B), then the other (C-D) --
the volée number does not change between them, only once *all* configured
relays for that end have shot does the engine move to the next volée.
Whether a match uses both relays or just one is a per-match setting
(``turn_mode``), fixed before the match starts and never toggled mid-match.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..models import Phase
from ..sequence import Step
from .base import ShootingMode

TURN_MODES = {
    "ab_then_cd": ["A-B", "C-D"],
    "ab_only": ["A-B"],
    "cd_only": ["C-D"],
}


@dataclass
class IndoorConfig:
    series: int = 2
    ends_per_series: int = 6
    arrows_per_end: int = 5

    prep_time: float = 15.0     # red: préparation / mise en place
    green_time: float = 90.0    # main shooting time
    orange_time: float = 30.0   # warning period (total shoot time = green+orange)

    distance_label: str = "18m"
    target_image: str = "wa_indoor_40cm.png"

    # Comment les archers se relaient sur un même blason pendant une volée :
    # "ab_then_cd" (les deux relais, l'un après l'autre), "ab_only" ou
    # "cd_only" (un seul relais). Fixé avant le match, ne change jamais en
    # cours de concours.
    turn_mode: str = "ab_then_cd"

    def __post_init__(self) -> None:
        if self.series < 1 or self.ends_per_series < 1 or self.arrows_per_end < 1:
            raise ValueError("series, ends_per_series and arrows_per_end must be >= 1")
        for name, value in (
            ("prep_time", self.prep_time),
            ("green_time", self.green_time),
            ("orange_time", self.orange_time),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        if self.turn_mode not in TURN_MODES:
            raise ValueError(
                f"turn_mode must be one of {sorted(TURN_MODES)}, got {self.turn_mode!r}"
            )


class IndoorMode(ShootingMode):
    def __init__(self, config: IndoorConfig | None = None) -> None:
        self.config = config or IndoorConfig()

    def build_sequence(self) -> List[Step]:
        cfg = self.config
        total_ends = cfg.series * cfg.ends_per_series
        relays = TURN_MODES[cfg.turn_mode]

        def relay_block(end_index: int, turn: str) -> List[Step]:
            common = dict(
                current_turn=turn,
                end_number=end_index,
                total_ends=total_ends,
                distance_label=cfg.distance_label,
                target_image=cfg.target_image,
            )
            block: List[Step] = []
            if cfg.prep_time > 0:
                block.append(Step(phase=Phase.RED, duration=cfg.prep_time,
                                   sound_event="prep_start", **common))
            block.append(Step(phase=Phase.GREEN, duration=cfg.green_time,
                               sound_event="shoot_start", **common))
            if cfg.orange_time > 0:
                block.append(Step(phase=Phase.ORANGE, duration=cfg.orange_time,
                                   sound_event="warning_orange", **common))
            return block

        steps: List[Step] = []
        for end_index in range(1, total_ends + 1):
            for turn in relays:
                # Le relais suivant (s'il y en a un) commence par son propre
                # RED de préparation -- pas besoin de PAUSE entre A-B et
                # C-D, ce n'est pas une récupération de flèches, juste un
                # changement de tireurs sur la ligne.
                steps.extend(relay_block(end_index, turn))

            has_next_end = end_index < total_ends
            if has_next_end:
                # Fin de volée (tous les relais ont tiré) : récupération
                # des flèches, pas de décompte. Le DOS déclenche la volée
                # suivante manuellement (next()).
                steps.append(Step(
                    phase=Phase.PAUSE, duration=None,
                    current_turn=relays[0], end_number=end_index + 1,
                    total_ends=total_ends,
                    distance_label=cfg.distance_label, target_image=cfg.target_image,
                ))
        return steps

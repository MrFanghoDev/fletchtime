"""Indoor round: fixed number of series, each made of several ends of a
fixed number of arrows, all shot at a single distance. Matches the club's
concours format ("2 séries de 6 volées de 5 flèches") but every number is
configurable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..models import Phase
from ..sequence import Step
from .base import ShootingMode


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

    rotate_turn: bool = True    # alternate A-B / C-D each end

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


class IndoorMode(ShootingMode):
    def __init__(self, config: IndoorConfig | None = None) -> None:
        self.config = config or IndoorConfig()

    def build_sequence(self) -> List[Step]:
        cfg = self.config
        total_ends = cfg.series * cfg.ends_per_series
        turn_cycle = ["A-B", "C-D"] if cfg.rotate_turn else [""]

        def common_for(end_index: int) -> dict:
            turn = turn_cycle[(end_index - 1) % len(turn_cycle)]
            return dict(
                current_turn=turn,
                end_number=end_index,
                total_ends=total_ends,
                distance_label=cfg.distance_label,
                target_image=cfg.target_image,
            )

        steps: List[Step] = []
        for end_index in range(1, total_ends + 1):
            common = common_for(end_index)
            if cfg.prep_time > 0:
                steps.append(Step(phase=Phase.RED, duration=cfg.prep_time,
                                   sound_event="prep_start", **common))
            steps.append(Step(phase=Phase.GREEN, duration=cfg.green_time,
                               sound_event="shoot_start", **common))
            if cfg.orange_time > 0:
                steps.append(Step(phase=Phase.ORANGE, duration=cfg.orange_time,
                                   sound_event="warning_orange", **common))

            has_next_end = end_index < total_ends
            if has_next_end:
                # Fin de volée : récupération des flèches, pas de décompte.
                # Le DOS déclenche la volée suivante manuellement (next()).
                # Les métadonnées annoncent déjà la volée à venir.
                steps.append(Step(phase=Phase.PAUSE, duration=None,
                                   **common_for(end_index + 1)))
        return steps

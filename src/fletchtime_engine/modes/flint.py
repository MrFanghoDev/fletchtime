"""Flint round (FFTL): each "unité standard" is 6 standard ends (4 arrows,
one fixed distance, ~3 minutes) followed by one "walk-up" end (4 arrows, 4
different distances, 45 seconds per arrow, the whole group advancing
together between arrows). A "parcours" is ``units`` unités standards
(2 for the club's competition).

A-B / C-D relays: unlike Indoor (where both relays share a target boss and
can swap within the same volée), Flint's field-style single-lane course
means swapping relays mid-volée isn't practical or safe -- there's no room
for two target faces per distance, and moving people between shooting
positions repeatedly would be dangerous. So here, a relay shoots an entire
unité standard (all 7 volées) before the other relay repeats that same
unité from its own start. Which relays are used, and in which order, is
fixed before the match starts (``turn_mode``) and never changed mid-match.

See docs/specifications.md for the full rule text this is derived from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..models import Phase
from ..sequence import Step
from ..turn_modes import TURN_MODES
from .base import ShootingMode


@dataclass
class FlintConfig:
    units: int = 2  # a "parcours" = this many unités standards

    standard_ends_per_unit: int = 6
    arrows_per_standard_end: int = 4
    standard_prep_time: float = 10.0
    standard_shoot_time: float = 180.0          # temps de tir total, continu (3 min)
    standard_orange_warning_time: float = 20.0  # passage à l'orange sans reset du décompte
    standard_distances: List[str] = field(default_factory=lambda: [
        "25 yards", "20 pieds", "30 yards", "15 yards", "20 yards", "10 yards",
    ])
    standard_target_image: str = "field_20cm.png"

    walkup_arrows: int = 4
    walkup_time_per_arrow: float = 45.0
    walkup_prep_time: float = 10.0
    walkup_distances: List[str] = field(default_factory=lambda: [
        "30 yards", "25 yards", "20 yards", "15 yards",
    ])
    walkup_target_image: str = "field_20cm.png"

    # Comment les archers se relaient sur le parcours : "ab_then_cd",
    # "cd_then_ab" (les deux relais, un après l'autre -- chacun tirant
    # l'unité ENTIÈRE avant que l'autre ne la reprenne), "ab_only" ou
    # "cd_only" (un seul relais). Ceci fixe l'ordre de la *première* unité ;
    # fixé avant le match, ne change jamais en cours de concours.
    turn_mode: str = "ab_then_cd"

    # Le concours du club alterne l'ordre des relais d'une unité à l'autre
    # (unité 1 : A-B puis C-D -- unité 2 : C-D puis A-B), exactement comme
    # pour l'Indoor. Sans effet sur "ab_only"/"cd_only".
    alternate_relay_order_each_unit: bool = True

    def __post_init__(self) -> None:
        if self.units < 1:
            raise ValueError("units must be >= 1")
        if len(self.standard_distances) != self.standard_ends_per_unit:
            raise ValueError(
                "standard_distances must have exactly standard_ends_per_unit "
                f"entries ({self.standard_ends_per_unit}), got "
                f"{len(self.standard_distances)}"
            )
        if len(self.walkup_distances) != self.walkup_arrows:
            raise ValueError(
                "walkup_distances must have exactly walkup_arrows entries "
                f"({self.walkup_arrows}), got {len(self.walkup_distances)}"
            )
        for name, value in (
            ("standard_prep_time", self.standard_prep_time),
            ("standard_shoot_time", self.standard_shoot_time),
            ("standard_orange_warning_time", self.standard_orange_warning_time),
            ("walkup_time_per_arrow", self.walkup_time_per_arrow),
            ("walkup_prep_time", self.walkup_prep_time),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        if self.standard_orange_warning_time > self.standard_shoot_time:
            raise ValueError(
                "standard_orange_warning_time must be <= standard_shoot_time, got "
                f"{self.standard_orange_warning_time} > {self.standard_shoot_time}"
            )
        if self.turn_mode not in TURN_MODES:
            raise ValueError(
                f"turn_mode must be one of {sorted(TURN_MODES)}, got {self.turn_mode!r}"
            )


class FlintMode(ShootingMode):
    def __init__(self, config: FlintConfig | None = None) -> None:
        self.config = config or FlintConfig()

    def _relays_for_unit(self, unit: int) -> List[str]:
        cfg = self.config
        base = TURN_MODES[cfg.turn_mode]
        if cfg.alternate_relay_order_each_unit and len(base) == 2 and unit % 2 == 0:
            return list(reversed(base))
        return base

    def build_sequence(self) -> List[Step]:
        cfg = self.config
        total_ends_per_unit = cfg.standard_ends_per_unit + 1  # +1 for walk-up end
        walkup_end_number = cfg.standard_ends_per_unit + 1

        # Build one "block" per end (a block = the steps for that end, with
        # no pause inside it -- the walk-up's 4 arrows stay contiguous).
        # For each unit, every relay shoots the *entire* unit (volées 1..7)
        # before the next relay repeats it from volée 1 again. Which relay
        # goes first can alternate from one unit to the next (see
        # ``alternate_relay_order_each_unit``), e.g. the club's real
        # competition: unité 1 = A-B puis C-D, unité 2 = C-D puis A-B.
        end_blocks: List[List[Step]] = []
        for unit in range(1, cfg.units + 1):
            for turn in self._relays_for_unit(unit):
                for end_index in range(1, cfg.standard_ends_per_unit + 1):
                    end_blocks.append(
                        self._standard_end(cfg, unit, end_index, total_ends_per_unit, turn)
                    )
                end_blocks.append(
                    self._walkup_end(cfg, unit, total_ends_per_unit, walkup_end_number, turn)
                )

        steps: List[Step] = []
        for i, block in enumerate(end_blocks):
            steps.extend(block)
            if i + 1 < len(end_blocks):
                # Fin de volée (ou fin du passage d'un relais) : récupération
                # des flèches / changement de relais, pas de décompte. Le
                # DOS déclenche la suite manuellement (next()).
                next_step = end_blocks[i + 1][0]
                steps.append(Step(
                    phase=Phase.PAUSE, duration=None,
                    current_turn=next_step.current_turn,
                    end_number=next_step.end_number,
                    total_ends=next_step.total_ends,
                    unit_number=next_step.unit_number,
                    arrow_in_end=next_step.arrow_in_end,
                    total_arrows_in_end=next_step.total_arrows_in_end,
                    distance_label=next_step.distance_label,
                    target_image=next_step.target_image,
                ))
        return steps

    @staticmethod
    def _standard_end(cfg: FlintConfig, unit: int, end_index: int,
                       total_ends: int, turn: str) -> List[Step]:
        distance = cfg.standard_distances[end_index - 1]
        common = dict(
            current_turn=turn,
            end_number=end_index,
            total_ends=total_ends,
            unit_number=unit,
            distance_label=distance,
            target_image=cfg.standard_target_image,
        )
        steps: List[Step] = []
        if cfg.standard_prep_time > 0:
            steps.append(Step(phase=Phase.RED, duration=cfg.standard_prep_time,
                               sound_event="prep_start", **common))
        steps.append(Step(
            phase=Phase.GREEN, duration=cfg.standard_shoot_time,
            sound_event="shoot_start",
            orange_threshold=(cfg.standard_orange_warning_time
                               if cfg.standard_orange_warning_time > 0 else None),
            orange_sound_event="warning_orange",
            **common,
        ))
        return steps

    @staticmethod
    def _walkup_end(cfg: FlintConfig, unit: int, total_ends: int,
                     end_number: int, turn: str) -> List[Step]:
        steps: List[Step] = []
        for arrow_index in range(1, cfg.walkup_arrows + 1):
            distance = cfg.walkup_distances[arrow_index - 1]
            common = dict(
                current_turn=turn,
                end_number=end_number,
                total_ends=total_ends,
                unit_number=unit,
                arrow_in_end=arrow_index,
                total_arrows_in_end=cfg.walkup_arrows,
                distance_label=distance,
                target_image=cfg.walkup_target_image,
            )
            if cfg.walkup_prep_time > 0:
                steps.append(Step(phase=Phase.RED, duration=cfg.walkup_prep_time,
                                   sound_event="prep_start", **common))
            steps.append(Step(phase=Phase.GREEN, duration=cfg.walkup_time_per_arrow,
                               sound_event="shoot_start", **common))
        return steps

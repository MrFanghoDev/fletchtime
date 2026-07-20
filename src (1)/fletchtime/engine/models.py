"""Core data model shared by every shooting mode and by the match engine.

Deliberately dependency-free (stdlib only) so this package can be tested and
reused without pulling in FastAPI/websockets: the engine only produces
``MatchState`` snapshots, it says nothing about how they are transported.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Phase(StrEnum):
    """Visual/safety phase of the current step.

    - ``WAIT`` -- before the match starts, or between matches. No countdown.
    - ``RED`` -- preparation time (archers approach / take position).
    - ``GREEN`` -- main shooting time.
    - ``ORANGE`` -- warning period near the end of shooting time.
    - ``PAUSE`` -- end of a volée: archers retrieve arrows, no countdown.
      The engine waits here indefinitely until the DOS manually starts
      the next volée (``MatchEngine.next()``).
    - ``EMERGENCY`` -- danger signal, clock frozen, must be explicitly resumed.
    - ``FINISHED`` -- sequence exhausted, nothing left to shoot.
    """

    WAIT = "wait"
    RED = "red"
    GREEN = "green"
    ORANGE = "orange"
    PAUSE = "pause"
    EMERGENCY = "emergency"
    FINISHED = "finished"


@dataclass(frozen=True)
class MatchState:
    """Immutable snapshot of where the match currently stands.

    This is the object a transport layer (FastAPI/WebSocket) would serialize
    and push to display screens -- see docs/architecture.md.
    """

    phase: Phase = Phase.WAIT
    time_left: float = 0.0

    # sequencing / display context
    current_turn: str = ""  # e.g. "A-B", "C-D", "" if not applicable
    end_number: int = 0  # 1-indexed end/volée within the unit
    total_ends: int = 0  # total ends in the unit (incl. walk-up end)
    unit_number: int = 1  # for Flint: which "unité standard" (1..n)
    arrow_in_end: int = 0  # for walk-up ends: which arrow (1-indexed)
    total_arrows_in_end: int = 0  # for walk-up ends: arrows in this end

    distance_label: str = ""
    target_image: str = ""
    target_image_2: str = ""

    finished: bool = False

    # Seuil (en secondes de temps restant) à partir duquel la phase passe
    # à l'orange -- None si l'étape en cours n'a pas de seuil d'alerte
    # (ex. pause, urgence). Transmis aux écrans pour qu'ils puissent
    # reproduire localement le passage à l'orange pendant une coupure
    # réseau, voir fletchtime.server.match_server et docs/architecture.md.
    orange_threshold: float | None = None

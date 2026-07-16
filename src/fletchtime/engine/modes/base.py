"""Common interface for shooting modes.

Unlike the legacy ArcheryClock approach (a single 12k-line file dispatching
on a string like ``archerysystem = 'fita'`` in dozens of scattered ``if``
branches), each mode here is a self-contained class that only knows how to
build its own sequence of steps. Adding a new mode never touches existing
ones -- see docs/dev-guide for the walkthrough.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..sequence import Step


class ShootingMode(ABC):
    """Builds the full ordered list of :class:`Step` for one competition
    round. Modes are stateless sequence generators; all runtime state
    (current position, elapsed time, pause/emergency) lives in
    :class:`fletchtime.engine.engine.MatchEngine`.
    """

    @abstractmethod
    def build_sequence(self) -> List[Step]:
        """Return the ordered, non-empty list of steps for this round."""
        raise NotImplementedError

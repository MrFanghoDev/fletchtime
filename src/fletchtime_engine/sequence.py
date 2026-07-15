"""A ``Step`` is one timed segment of a competition (e.g. "red light, 10s,
end 3 of 12, turn A-B, distance 18m"). A shooting mode's job is only to
produce an ordered list of ``Step``s up front; the engine then plays that
list back, handling ticking, manual advance and emergency stop.

This keeps modes simple, declarative, and trivial to unit test: you can
assert on the exact list of steps a config produces without running any
timer at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import Phase


@dataclass(frozen=True)
class Step:
    """One timed segment of a match sequence.

    ``duration`` is normally a number of seconds. It can also be ``None``,
    meaning "wait here indefinitely until the DOS presses next" -- used for
    the PAUSE step inserted between volées, where archers retrieve arrows
    at their own pace.

    A GREEN step can carry an ``orange_threshold``: once ``duration``
    seconds have counted down to that many seconds remaining, the engine
    *displays* the step as ORANGE, but it stays the same step -- the
    countdown never resets or jumps, it's one continuous timer that just
    changes colour near the end (e.g. 240s total, orange in the last 30s).
    """

    phase: Phase
    duration: Optional[float]

    current_turn: str = ""
    end_number: int = 0
    total_ends: int = 0
    unit_number: int = 1
    arrow_in_end: int = 0
    total_arrows_in_end: int = 0

    distance_label: str = ""
    target_image: str = ""

    # identifier consumed by the transport layer to trigger a sound; not a
    # filename -- see docs/architecture.md "Packs de sons".
    sound_event: Optional[str] = None

    # seconds remaining at which the step's displayed phase switches from
    # GREEN to ORANGE, without resetting the countdown. None = no switch.
    orange_threshold: Optional[float] = None
    # sound event fired once, exactly when time_left crosses orange_threshold
    orange_sound_event: Optional[str] = None

    def __post_init__(self) -> None:
        if self.duration is not None and self.duration < 0:
            raise ValueError(f"Step duration must be >= 0 or None, got {self.duration}")
        if self.orange_threshold is not None:
            if self.orange_threshold < 0:
                raise ValueError(
                    f"orange_threshold must be >= 0, got {self.orange_threshold}"
                )
            if self.duration is not None and self.orange_threshold > self.duration:
                raise ValueError(
                    "orange_threshold must be <= duration, got "
                    f"orange_threshold={self.orange_threshold} > duration={self.duration}"
                )

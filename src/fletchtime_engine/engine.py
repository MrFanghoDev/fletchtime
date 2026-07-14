"""Plays back the ordered list of :class:`Step` produced by a
:class:`ShootingMode`, exposing the controls a DOS (Director Of Shooting)
needs: regular ticking, manual advance, emergency stop/resume, pause.

This is intentionally the only stateful class in the engine package -- modes
themselves stay pure/stateless so they are trivial to unit test in
isolation (see tests/test_indoor_mode.py, tests/test_flint_mode.py).
"""

from __future__ import annotations

from typing import List, Optional

from .models import MatchState, Phase
from .modes.base import ShootingMode
from .sequence import Step


class MatchEngine:
    def __init__(self, mode: ShootingMode) -> None:
        self._steps: List[Step] = mode.build_sequence()
        if not self._steps:
            raise ValueError("A shooting mode must produce at least one step")

        self._index = 0
        self._time_left: float = self._steps[0].duration
        self._finished = False
        self._paused = False
        self._message: Optional[str] = None

        self._emergency = False
        self._emergency_saved_time: Optional[float] = None

        self._pending_events: List[str] = []
        self._emit_current_step_event()

    # -- controls --------------------------------------------------------

    def tick(self, dt: float) -> MatchState:
        """Advance the clock by ``dt`` seconds. Call regularly (e.g. 10Hz).

        Safe to call with a ``dt`` larger than the remaining time on the
        current step: the engine will cascade through as many steps as
        needed (e.g. after a lag spike), matching the "catch up to real
        time" behaviour described in the ArcheryClock manual.
        """
        if self._emergency or self._paused or self._finished:
            return self.current_state

        self._time_left -= dt
        while self._time_left <= 0 and not self._finished:
            overflow = -self._time_left
            self._advance_step()
            if not self._finished:
                self._time_left -= overflow
        return self.current_state

    def next(self) -> MatchState:
        """Manual advance, as if the DOS pressed the "next" button."""
        if not self._emergency:
            self._advance_step()
        return self.current_state

    def emergency(self) -> MatchState:
        """Freeze the clock immediately. Position/time-left are remembered
        so :meth:`resume` can pick up where it left off."""
        if not self._emergency:
            self._emergency = True
            self._emergency_saved_time = self._time_left
        return self.current_state

    def resume(self, adjusted_time_left: Optional[float] = None) -> MatchState:
        """Recover from emergency. ``adjusted_time_left`` lets the DOS
        compensate the archers for time lost, per FFTL rules on equipment
        failure."""
        if self._emergency:
            self._emergency = False
            self._time_left = (
                adjusted_time_left if adjusted_time_left is not None
                else self._emergency_saved_time
            )
            self._emergency_saved_time = None
        return self.current_state

    def pause(self) -> MatchState:
        self._paused = True
        return self.current_state

    def play(self) -> MatchState:
        self._paused = False
        return self.current_state

    def set_message(self, message: Optional[str]) -> None:
        self._message = message

    def pop_pending_events(self) -> List[str]:
        """Return and clear sound events accumulated since the last call.

        Kept separate from ``current_state`` on purpose: an event (e.g.
        "shoot_start") should be broadcast exactly once, at the transition,
        not re-read on every tick.
        """
        events, self._pending_events = self._pending_events, []
        return events

    # -- internals ---------------------------------------------------------

    def _advance_step(self) -> None:
        if self._index + 1 >= len(self._steps):
            self._finished = True
            self._time_left = 0.0
        else:
            self._index += 1
            self._time_left = self._steps[self._index].duration
            self._emit_current_step_event()

    def _emit_current_step_event(self) -> None:
        event = self._steps[self._index].sound_event
        if event:
            self._pending_events.append(event)

    @property
    def current_state(self) -> MatchState:
        if self._finished:
            return MatchState(phase=Phase.FINISHED, finished=True, message=self._message)

        step = self._steps[self._index]
        phase = Phase.EMERGENCY if self._emergency else step.phase
        time_left = self._emergency_saved_time if self._emergency else self._time_left

        return MatchState(
            phase=phase,
            time_left=round(max(time_left, 0.0), 1),
            current_turn=step.current_turn,
            end_number=step.end_number,
            total_ends=step.total_ends,
            unit_number=step.unit_number,
            arrow_in_end=step.arrow_in_end,
            total_arrows_in_end=step.total_arrows_in_end,
            distance_label=step.distance_label,
            target_image=step.target_image,
            message=self._message,
            finished=False,
        )

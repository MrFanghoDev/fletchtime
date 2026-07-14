"""Plays back the ordered list of :class:`Step` produced by a
:class:`ShootingMode`, exposing the controls a DOS (Director Of Shooting)
needs: regular ticking, manual advance, stop, restart, jump to a specific
end, emergency stop/resume, temporary pause.

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
        self._time_left: Optional[float] = self._steps[0].duration
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
        time" behaviour described in the ArcheryClock manual. The cascade
        stops as soon as it lands on an indefinite (PAUSE) step: those
        never count down on their own, only :meth:`next` moves past them.
        """
        if self._emergency or self._paused or self._finished or self._time_left is None:
            return self.current_state

        self._time_left -= dt
        while self._time_left is not None and self._time_left <= 0 and not self._finished:
            overflow = -self._time_left
            self._advance_step()
            if self._finished or self._time_left is None:
                break
            self._time_left -= overflow
        return self.current_state

    def next(self) -> MatchState:
        """Manual advance, as if the DOS pressed the "next" button. This is
        how a PAUSE step (end of a volée, arrows being retrieved) is left:
        pressing next starts the following volée's preparation time."""
        if not self._emergency:
            self._advance_step()
        return self.current_state

    def stop(self) -> MatchState:
        """Hard stop: end the current match right now, regardless of where
        it is in the sequence. Distinct from :meth:`emergency` (which can
        be resumed) -- this is a deliberate abandon/cancel by the DOS."""
        self._finished = True
        self._time_left = 0.0
        return self.current_state

    def restart(self) -> MatchState:
        """Restart the whole match from its very first step, keeping the
        same mode/config."""
        self._index = 0
        self._time_left = self._steps[0].duration
        self._finished = False
        self._paused = False
        self._emergency = False
        self._emergency_saved_time = None
        self._pending_events = []
        self._emit_current_step_event()
        return self.current_state

    def goto(self, unit_number: int, end_number: int, arrow_in_end: int = 0) -> MatchState:
        """Jump to a specific volée (and, for a walk-up end, optionally a
        specific arrow). Lands on the PAUSE step immediately preceding it
        when one exists -- more practical for the DOS: the screen already
        previews the target end/distance, and the countdown only actually
        starts once ``next()`` is pressed. Falls back to the shooting step
        itself when there is no preceding pause (e.g. the very first end
        of the match, or an individual walk-up arrow after the first).
        Raises ``ValueError`` if no step matches."""
        for index, step in enumerate(self._steps):
            if step.phase == Phase.PAUSE:
                continue
            if step.unit_number != unit_number or step.end_number != end_number:
                continue
            if arrow_in_end and step.arrow_in_end != arrow_in_end:
                continue

            target_index = index
            if index > 0 and self._steps[index - 1].phase == Phase.PAUSE:
                target_index = index - 1

            self._index = target_index
            self._time_left = self._steps[target_index].duration
            self._finished = False
            self._paused = False
            self._emergency = False
            self._emergency_saved_time = None
            self._pending_events = []
            self._emit_current_step_event()
            return self.current_state
        raise ValueError(
            f"No step found for unit={unit_number} end={end_number} "
            f"arrow={arrow_in_end or '-'}"
        )

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
            time_left=round(max(time_left, 0.0), 1) if time_left is not None else 0.0,
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

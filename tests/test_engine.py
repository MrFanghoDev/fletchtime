import unittest

from fletchtime_engine import (
    FlintConfig,
    FlintMode,
    IndoorConfig,
    IndoorMode,
    MatchEngine,
    Phase,
)


def simple_indoor_engine() -> MatchEngine:
    cfg = IndoorConfig(series=1, ends_per_series=2, prep_time=10,
                        green_time=90, orange_time=30, rotate_turn=True)
    return MatchEngine(IndoorMode(cfg))


class TestMatchEngineTicking(unittest.TestCase):
    def test_initial_state_is_first_step(self) -> None:
        engine = simple_indoor_engine()
        state = engine.current_state
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.time_left, 10)
        self.assertEqual(state.end_number, 1)
        self.assertEqual(state.current_turn, "A-B")

    def test_tick_counts_down_within_a_step(self) -> None:
        engine = simple_indoor_engine()
        state = engine.tick(3)
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.time_left, 7)

    def test_tick_crosses_into_next_step_exactly(self) -> None:
        engine = simple_indoor_engine()
        state = engine.tick(10)  # exactly the RED duration
        self.assertEqual(state.phase, Phase.GREEN)
        self.assertEqual(state.time_left, 90)

    def test_tick_cascades_through_multiple_steps_after_lag(self) -> None:
        """A single large dt (e.g. after the process was suspended) should
        still land on the correct step, not just clamp to 0."""
        engine = simple_indoor_engine()
        # RED(10) + GREEN(90) + ORANGE(30) = 130s for end 1, then RED(10) of end 2
        state = engine.tick(135)
        self.assertEqual(state.end_number, 2)
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.time_left, 5)  # 10 - (135-130)

    def test_reaching_the_end_of_sequence_finishes(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, prep_time=1,
                            green_time=1, orange_time=1, rotate_turn=False)
        engine = MatchEngine(IndoorMode(cfg))
        state = engine.tick(3)  # exactly consumes the only end
        self.assertTrue(state.finished)
        self.assertEqual(state.phase, Phase.FINISHED)

        # further ticks must not raise or move past "finished"
        state = engine.tick(100)
        self.assertTrue(state.finished)


class TestMatchEngineManualControl(unittest.TestCase):
    def test_next_advances_to_next_step_regardless_of_time_left(self) -> None:
        engine = simple_indoor_engine()
        state = engine.next()
        self.assertEqual(state.phase, Phase.GREEN)
        self.assertEqual(state.time_left, 90)

    def test_next_through_full_end_changes_turn(self) -> None:
        engine = simple_indoor_engine()
        for _ in range(3):  # RED -> GREEN -> ORANGE -> (next end) RED
            state = engine.next()
        self.assertEqual(state.end_number, 2)
        self.assertEqual(state.current_turn, "C-D")
        self.assertEqual(state.phase, Phase.RED)


class TestMatchEngineEmergency(unittest.TestCase):
    def test_emergency_freezes_the_clock(self) -> None:
        engine = simple_indoor_engine()
        engine.tick(4)  # time_left now 6
        state = engine.emergency()
        self.assertEqual(state.phase, Phase.EMERGENCY)
        self.assertEqual(state.time_left, 6)

        # ticking further must not change anything while frozen
        state = engine.tick(50)
        self.assertEqual(state.phase, Phase.EMERGENCY)
        self.assertEqual(state.time_left, 6)

    def test_next_is_ignored_during_emergency(self) -> None:
        engine = simple_indoor_engine()
        engine.emergency()
        state = engine.next()
        self.assertEqual(state.phase, Phase.EMERGENCY)

    def test_resume_restores_saved_time_by_default(self) -> None:
        engine = simple_indoor_engine()
        engine.tick(4)
        engine.emergency()
        state = engine.resume()
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.time_left, 6)

    def test_resume_can_adjust_time_left(self) -> None:
        """FFTL rule: compensate archers for time lost to equipment failure."""
        engine = simple_indoor_engine()
        engine.tick(4)
        engine.emergency()
        state = engine.resume(adjusted_time_left=10)
        self.assertEqual(state.time_left, 10)


class TestMatchEnginePauseAndMessage(unittest.TestCase):
    def test_pause_stops_ticking_and_play_resumes_it(self) -> None:
        engine = simple_indoor_engine()
        engine.pause()
        state = engine.tick(5)
        self.assertEqual(state.time_left, 10)  # unchanged

        engine.play()
        state = engine.tick(5)
        self.assertEqual(state.time_left, 5)

    def test_message_is_attached_to_every_state_until_cleared(self) -> None:
        engine = simple_indoor_engine()
        engine.set_message("Retard de 10 minutes, prochaine manche à 14h10")
        state = engine.tick(1)
        self.assertEqual(state.message, "Retard de 10 minutes, prochaine manche à 14h10")

        engine.set_message(None)
        state = engine.tick(1)
        self.assertIsNone(state.message)


class TestMatchEngineSoundEvents(unittest.TestCase):
    def test_first_step_event_is_pending_immediately(self) -> None:
        engine = simple_indoor_engine()
        self.assertEqual(engine.pop_pending_events(), ["prep_start"])

    def test_events_are_consumed_once(self) -> None:
        engine = simple_indoor_engine()
        engine.pop_pending_events()  # drain initial event
        self.assertEqual(engine.pop_pending_events(), [])

    def test_tick_transition_emits_new_step_event(self) -> None:
        engine = simple_indoor_engine()
        engine.pop_pending_events()
        engine.tick(10)  # crosses RED -> GREEN
        self.assertEqual(engine.pop_pending_events(), ["shoot_start"])

    def test_cascading_tick_emits_all_crossed_events_in_order(self) -> None:
        engine = simple_indoor_engine()
        engine.pop_pending_events()
        engine.tick(135)  # RED->GREEN->ORANGE->(end2)RED
        self.assertEqual(
            engine.pop_pending_events(),
            ["shoot_start", "warning_orange", "prep_start"],
        )


class TestMatchEngineWithFlintMode(unittest.TestCase):
    def test_engine_plays_through_a_full_flint_unit(self) -> None:
        cfg = FlintConfig(units=1)
        engine = MatchEngine(FlintMode(cfg))

        # play through all 6 standard ends (RED+GREEN+ORANGE each) via next()
        for _ in range(6 * 3):
            engine.next()

        state = engine.current_state
        self.assertEqual(state.end_number, 7)  # walk-up end
        self.assertEqual(state.arrow_in_end, 1)
        self.assertEqual(state.phase, Phase.RED)

    def test_walkup_arrows_play_back_to_back_without_looping(self) -> None:
        cfg = FlintConfig(units=1)
        engine = MatchEngine(FlintMode(cfg))
        for _ in range(6 * 3):  # skip to the walk-up end
            engine.next()

        seen_arrows = []
        for _ in range(8):  # 4 arrows x (RED, GREEN)
            state = engine.current_state
            if state.phase == Phase.GREEN:
                seen_arrows.append(state.arrow_in_end)
            engine.next()

        self.assertEqual(seen_arrows, [1, 2, 3, 4])
        self.assertTrue(engine.current_state.finished)


if __name__ == "__main__":
    unittest.main()

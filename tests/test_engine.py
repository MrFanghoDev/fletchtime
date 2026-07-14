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
                        green_time=90, orange_time=30, turn_mode="ab_only")
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
        still land on the correct step -- but never skip past a PAUSE step:
        the end of a volée always requires a manual next(), no matter how
        large the elapsed time was."""
        engine = simple_indoor_engine()
        # RED(10) + GREEN(90) + ORANGE(30) = 130s for end 1, then PAUSE
        # (indefinite) before end 2 -- a huge dt must stop there, not
        # auto-start end 2.
        state = engine.tick(135)
        self.assertEqual(state.phase, Phase.PAUSE)
        self.assertEqual(state.end_number, 2)  # preview of the upcoming end
        self.assertEqual(state.time_left, 0.0)

        # only a manual next() actually starts end 2
        state = engine.next()
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.end_number, 2)
        self.assertEqual(state.time_left, 10)

    def test_reaching_the_end_of_sequence_finishes(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, prep_time=1,
                            green_time=1, orange_time=1, turn_mode="ab_only")
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

    def test_next_through_full_end_reaches_pause_previewing_next_end(self) -> None:
        engine = simple_indoor_engine()
        for _ in range(3):  # RED -> GREEN -> ORANGE -> PAUSE (preview end 2)
            state = engine.next()
        self.assertEqual(state.phase, Phase.PAUSE)
        self.assertEqual(state.end_number, 2)

        state = engine.next()  # DOS starts end 2
        self.assertEqual(state.end_number, 2)
        self.assertEqual(state.phase, Phase.RED)

    def test_ab_then_cd_relay_within_the_same_end_via_next(self) -> None:
        """A-B et C-D tirent la même volée : le numéro ne doit pas changer
        entre les deux relais, seul le tireur actif change."""
        cfg = IndoorConfig(series=1, ends_per_series=2, prep_time=10,
                            green_time=90, orange_time=30, turn_mode="ab_then_cd")
        engine = MatchEngine(IndoorMode(cfg))

        state = engine.current_state
        self.assertEqual(state.current_turn, "A-B")
        self.assertEqual(state.end_number, 1)

        for _ in range(3):  # RED->GREEN->ORANGE of A-B's relay
            state = engine.next()
        self.assertEqual(state.phase, Phase.RED)  # C-D's own prep, same end
        self.assertEqual(state.current_turn, "C-D")
        self.assertEqual(state.end_number, 1)  # unchanged -- still volée 1

        for _ in range(3):  # RED->GREEN->ORANGE of C-D's relay
            state = engine.next()
        self.assertEqual(state.phase, Phase.PAUSE)  # now end 1 is truly over
        self.assertEqual(state.end_number, 2)  # preview of end 2
        self.assertEqual(state.current_turn, "A-B")  # end 2 restarts with A-B


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


class TestMatchEnginePause(unittest.TestCase):
    def test_pause_stops_ticking_and_play_resumes_it(self) -> None:
        engine = simple_indoor_engine()
        engine.pause()
        state = engine.tick(5)
        self.assertEqual(state.time_left, 10)  # unchanged

        engine.play()
        state = engine.tick(5)
        self.assertEqual(state.time_left, 5)


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
        engine.tick(135)  # RED->GREEN->ORANGE->PAUSE (stops there, no event)
        self.assertEqual(
            engine.pop_pending_events(),
            ["shoot_start", "warning_orange"],
        )


class TestMatchEngineWithFlintMode(unittest.TestCase):
    def test_engine_plays_through_a_full_flint_unit(self) -> None:
        cfg = FlintConfig(units=1)
        engine = MatchEngine(FlintMode(cfg))

        # each standard end is RED+GREEN+ORANGE+PAUSE (4 steps); play through
        # all 6 via next(), landing exactly on the walk-up end's first arrow
        for _ in range(6 * 4):
            engine.next()

        state = engine.current_state
        self.assertEqual(state.end_number, 7)  # walk-up end
        self.assertEqual(state.arrow_in_end, 1)
        self.assertEqual(state.phase, Phase.RED)

    def test_walkup_arrows_play_back_to_back_without_looping(self) -> None:
        cfg = FlintConfig(units=1)
        engine = MatchEngine(FlintMode(cfg))
        for _ in range(6 * 4):  # skip to the walk-up end (see test above)
            engine.next()

        seen_arrows = []
        for _ in range(8):  # 4 arrows x (RED, GREEN)
            state = engine.current_state
            if state.phase == Phase.GREEN:
                seen_arrows.append(state.arrow_in_end)
            engine.next()

        self.assertEqual(seen_arrows, [1, 2, 3, 4])
        self.assertTrue(engine.current_state.finished)


class TestMatchEngineStopRestartGoto(unittest.TestCase):
    def test_stop_ends_the_match_immediately(self) -> None:
        engine = simple_indoor_engine()
        engine.tick(3)
        state = engine.stop()
        self.assertTrue(state.finished)
        self.assertEqual(state.phase, Phase.FINISHED)

        # further ticks/next must not resurrect the match
        self.assertTrue(engine.tick(5).finished)
        self.assertTrue(engine.next().finished)

    def test_restart_goes_back_to_the_very_first_step(self) -> None:
        engine = simple_indoor_engine()
        for _ in range(5):  # move well into the match
            engine.next()
        state = engine.restart()

        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.end_number, 1)
        self.assertEqual(state.current_turn, "A-B")
        self.assertEqual(state.time_left, 10)

    def test_restart_re_emits_the_first_step_event(self) -> None:
        engine = simple_indoor_engine()
        engine.next()
        engine.pop_pending_events()
        engine.restart()
        self.assertEqual(engine.pop_pending_events(), ["prep_start"])

    def test_restart_clears_emergency_and_finished_state(self) -> None:
        engine = simple_indoor_engine()
        engine.stop()
        state = engine.restart()
        self.assertFalse(state.finished)
        self.assertEqual(state.phase, Phase.RED)

    def test_goto_lands_on_the_pause_preview_before_the_target_end(self) -> None:
        cfg = FlintConfig(units=1)
        engine = MatchEngine(FlintMode(cfg))
        state = engine.goto(unit_number=1, end_number=3)

        self.assertEqual(state.phase, Phase.PAUSE)
        self.assertEqual(state.end_number, 3)
        self.assertEqual(state.distance_label, "15 yards")

        # DOS presses next() when ready -- that's what actually starts it
        state = engine.next()
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.end_number, 3)

    def test_goto_the_very_first_end_has_no_preview_pause_to_land_on(self) -> None:
        cfg = FlintConfig(units=1)
        engine = MatchEngine(FlintMode(cfg))
        state = engine.goto(unit_number=1, end_number=1)
        self.assertEqual(state.phase, Phase.RED)  # nothing precedes end 1

    def test_goto_can_target_a_specific_walkup_arrow(self) -> None:
        cfg = FlintConfig(units=1)
        engine = MatchEngine(FlintMode(cfg))
        # arrow 1 has a preview pause (announcing the whole walk-up end)
        state = engine.goto(unit_number=1, end_number=7, arrow_in_end=1)
        self.assertEqual(state.phase, Phase.PAUSE)
        self.assertEqual(state.arrow_in_end, 1)

        # arrows 2-4 don't (continuous walk-up, no retrieval in between)
        state = engine.goto(unit_number=1, end_number=7, arrow_in_end=3)
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.arrow_in_end, 3)
        self.assertEqual(state.distance_label, "20 yards")

    def test_goto_unknown_target_raises(self) -> None:
        engine = simple_indoor_engine()
        with self.assertRaises(ValueError):
            engine.goto(unit_number=1, end_number=99)

    def test_goto_clears_finished_and_emergency_state(self) -> None:
        engine = simple_indoor_engine()
        engine.stop()
        state = engine.goto(unit_number=1, end_number=1)
        self.assertFalse(state.finished)
        self.assertEqual(state.phase, Phase.RED)


if __name__ == "__main__":
    unittest.main()

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
                        shoot_time=120, orange_warning_time=30, turn_mode="ab_only")
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
        self.assertEqual(state.time_left, 120)

    def test_tick_cascades_through_multiple_steps_after_lag(self) -> None:
        """A single large dt (e.g. after the process was suspended) should
        still land on the correct step -- but never skip past a PAUSE step:
        the end of a volée always requires a manual next(), no matter how
        large the elapsed time was."""
        engine = simple_indoor_engine()
        # RED(10) + GREEN(120, continuous) = 130s for end 1, then PAUSE
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
                            shoot_time=1, orange_warning_time=1, turn_mode="ab_only")
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
        self.assertEqual(state.time_left, 120)

    def test_next_through_full_end_reaches_pause_previewing_next_end(self) -> None:
        engine = simple_indoor_engine()
        for _ in range(2):  # RED -> GREEN -> PAUSE (preview end 2)
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
                            shoot_time=90, orange_warning_time=30, turn_mode="ab_then_cd")
        engine = MatchEngine(IndoorMode(cfg))

        state = engine.current_state
        self.assertEqual(state.current_turn, "A-B")
        self.assertEqual(state.end_number, 1)

        for _ in range(2):  # RED -> GREEN of A-B's relay
            state = engine.next()
        self.assertEqual(state.phase, Phase.RED)  # C-D's own prep, same end
        self.assertEqual(state.current_turn, "C-D")
        self.assertEqual(state.end_number, 1)  # unchanged -- still volée 1

        for _ in range(2):  # RED -> GREEN of C-D's relay
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
        # RED(10)->GREEN(120)->PAUSE: the overshoot lands past the orange
        # window straight into the indefinite PAUSE, so no "warning_orange"
        # fires here -- see test_orange_threshold_* below for the normal,
        # non-overshooting case. Landing on PAUSE does fire "end_of_volee".
        engine.tick(135)
        self.assertEqual(engine.pop_pending_events(), ["shoot_start", "end_of_volee"])

    def test_orange_threshold_switches_phase_without_resetting_the_countdown(self) -> None:
        """Le point central du correctif : un seul décompte continu de
        120s, qui passe juste à l'orange dans les 30 dernières secondes --
        pas de redémarrage ni de saut de valeur affichée."""
        engine = simple_indoor_engine()
        engine.tick(10)  # enter GREEN(120)
        state = engine.tick(85)  # 120 - 85 = 35s left, still green
        self.assertEqual(state.phase, Phase.GREEN)
        self.assertEqual(state.time_left, 35)

        state = engine.tick(6)  # 35 - 6 = 29s left, crosses the 30s threshold
        self.assertEqual(state.phase, Phase.ORANGE)
        self.assertEqual(state.time_left, 29)  # continuous, no jump/reset
        self.assertEqual(state.end_number, 1)  # same volée throughout

    def test_orange_threshold_sound_event_fires_once(self) -> None:
        engine = simple_indoor_engine()
        engine.tick(10)  # enter GREEN
        engine.pop_pending_events()

        engine.tick(91)  # 120 - 91 = 29s left, crosses the 30s threshold
        self.assertEqual(engine.pop_pending_events(), ["warning_orange"])

        engine.tick(5)  # still under threshold, must not re-fire
        self.assertEqual(engine.pop_pending_events(), [])

    def test_emergency_and_resume_fire_distinct_sounds(self) -> None:
        engine = simple_indoor_engine()
        engine.pop_pending_events()

        engine.emergency()
        self.assertEqual(engine.pop_pending_events(), ["emergency_start"])

        engine.resume()
        self.assertEqual(engine.pop_pending_events(), ["emergency_end"])

    def test_emergency_sound_only_fires_once_even_if_called_again(self) -> None:
        engine = simple_indoor_engine()
        engine.pop_pending_events()
        engine.emergency()
        engine.pop_pending_events()

        engine.emergency()  # already in emergency, no-op
        self.assertEqual(engine.pop_pending_events(), [])

    def test_stop_fires_end_of_match(self) -> None:
        engine = simple_indoor_engine()
        engine.pop_pending_events()
        engine.stop()
        self.assertEqual(engine.pop_pending_events(), ["end_of_match"])

    def test_reaching_the_natural_end_fires_end_of_match(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, prep_time=1,
                            shoot_time=1, orange_warning_time=0, turn_mode="ab_only")
        engine = MatchEngine(IndoorMode(cfg))
        engine.pop_pending_events()
        state = engine.tick(3)  # exactly consumes the only end
        self.assertTrue(state.finished)
        self.assertIn("end_of_match", engine.pop_pending_events())

    def test_landing_on_pause_fires_end_of_volee(self) -> None:
        engine = simple_indoor_engine()
        engine.next()  # RED -> GREEN
        engine.pop_pending_events()
        state = engine.next()  # GREEN -> PAUSE
        self.assertEqual(state.phase, Phase.PAUSE)
        self.assertEqual(engine.pop_pending_events(), ["end_of_volee"])

    def test_countdown_ticks_fire_once_per_second_for_the_last_five(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=2, prep_time=10,
                            shoot_time=120, orange_warning_time=0, turn_mode="ab_only")
        engine = MatchEngine(IndoorMode(cfg))
        engine.tick(10)  # enter GREEN(120)
        engine.pop_pending_events()

        engine.tick(114)  # 120 - 114 = 6s left, not yet in the last 5
        self.assertEqual(engine.pop_pending_events(), [])

        events = []
        for _ in range(6):  # 6s -> 5,4,3,2,1,0 : one tick per second
            state = engine.tick(1)
            events.extend(engine.pop_pending_events())
        self.assertEqual(events.count("countdown_tick"), 5)
        self.assertEqual(state.time_left, 0)

    def test_countdown_tick_does_not_refire_within_the_same_second(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=2, prep_time=10,
                            shoot_time=120, orange_warning_time=0, turn_mode="ab_only")
        engine = MatchEngine(IndoorMode(cfg))
        engine.pop_pending_events()  # drain initial prep_start
        engine.tick(10)  # enter GREEN
        engine.pop_pending_events()  # drain shoot_start

        engine.tick(115.4)  # 120 - 115.4 = 4.6s left, crosses the "5" tick
        self.assertEqual(engine.pop_pending_events(), ["countdown_tick"])

        engine.tick(0.3)  # 4.6 - 0.3 = 4.3s -- still within the "4" bucket,
        # no new integer boundary crossed yet
        self.assertEqual(engine.pop_pending_events(), [])

    def test_countdown_ticks_reset_on_restart(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=2, prep_time=10,
                            shoot_time=120, orange_warning_time=0, turn_mode="ab_only")
        engine = MatchEngine(IndoorMode(cfg))
        engine.tick(10)
        engine.tick(116)  # well into the last 5 seconds, several ticks fired
        engine.pop_pending_events()

        engine.restart()
        engine.pop_pending_events()  # drain the initial prep_start
        engine.next()  # RED -> GREEN
        engine.pop_pending_events()
        engine.tick(116)  # should be able to fire the same ticks again
        self.assertIn("countdown_tick", engine.pop_pending_events())


class TestMatchEngineWithFlintMode(unittest.TestCase):
    def test_walkup_arrow_switches_to_orange_with_10s_left(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        engine = MatchEngine(FlintMode(cfg))
        for _ in range(6 * 3):  # skip to the walk-up end's first arrow
            engine.next()
        engine.next()  # leave the arrow's RED prep, enter GREEN(45, orange@10)

        state = engine.tick(34)  # 45 - 34 = 11s left, still green
        self.assertEqual(state.phase, Phase.GREEN)
        self.assertEqual(state.time_left, 11)

        state = engine.tick(1)  # 11 - 1 = 10s left, crosses the threshold
        self.assertEqual(state.phase, Phase.ORANGE)
        self.assertEqual(state.time_left, 10)
        self.assertEqual(state.arrow_in_end, 1)  # same arrow throughout

    def test_engine_plays_through_a_full_flint_unit(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        engine = MatchEngine(FlintMode(cfg))

        # each standard end is RED+GREEN(continu)+PAUSE (3 steps); play
        # through all 6 via next(), landing on the walk-up end's first arrow
        for _ in range(6 * 3):
            engine.next()

        state = engine.current_state
        self.assertEqual(state.end_number, 7)  # walk-up end
        self.assertEqual(state.arrow_in_end, 1)
        self.assertEqual(state.phase, Phase.RED)

    def test_walkup_arrows_play_back_to_back_without_looping(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        engine = MatchEngine(FlintMode(cfg))
        for _ in range(6 * 3):  # skip to the walk-up end (see test above)
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
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        engine = MatchEngine(FlintMode(cfg))
        state = engine.goto(unit_number=1, end_number=3)

        self.assertEqual(state.phase, Phase.PAUSE)
        self.assertEqual(state.end_number, 3)
        self.assertEqual(state.distance_label, "30 yards")

        # DOS presses next() when ready -- that's what actually starts it
        state = engine.next()
        self.assertEqual(state.phase, Phase.RED)
        self.assertEqual(state.end_number, 3)

    def test_goto_the_very_first_end_has_no_preview_pause_to_land_on(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        engine = MatchEngine(FlintMode(cfg))
        state = engine.goto(unit_number=1, end_number=1)
        self.assertEqual(state.phase, Phase.RED)  # nothing precedes end 1

    def test_goto_can_target_a_specific_walkup_arrow(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
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

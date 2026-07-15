import unittest

from fletchtime_engine import IndoorConfig, IndoorMode, Phase


class TestIndoorMode(unittest.TestCase):
    def test_default_config_matches_club_competition(self) -> None:
        """2 séries de 6 volées de 5 flèches : série 1 en A-B puis C-D,
        série 2 en C-D puis A-B (alternance activée par défaut)."""
        mode = IndoorMode()
        steps = mode.build_sequence()

        # each end = 2 relais x (RED + GREEN continu) = 4 steps, plus une
        # PAUSE après chaque volée sauf la toute dernière du match (2 séries
        # x 6 volées = 12 global ends, 11 pauses).
        self.assertEqual(len(steps), 12 * 4 + 11)

        series_numbers = sorted({s.unit_number for s in steps})
        self.assertEqual(series_numbers, [1, 2])

        end_numbers_in_series1 = sorted({s.end_number for s in steps if s.unit_number == 1})
        self.assertEqual(end_numbers_in_series1, [1, 2, 3, 4, 5, 6])
        self.assertTrue(all(s.total_ends == 6 for s in steps))

    def test_series_and_volee_are_distinct_fields(self) -> None:
        mode = IndoorMode(IndoorConfig(series=2, ends_per_series=6))
        steps = mode.build_sequence()

        series2_first_end = next(s for s in steps if s.unit_number == 2)
        self.assertEqual(series2_first_end.end_number, 1)  # pas 7

    def test_shoot_time_is_a_single_continuous_step(self) -> None:
        """Le point central du correctif : un seul step GREEN de 240s, pas
        deux steps successifs (vert puis orange) qui redémarreraient le
        décompte."""
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="ab_only")
        steps = IndoorMode(cfg).build_sequence()

        green_steps = [s for s in steps if s.phase == Phase.GREEN]
        self.assertEqual(len(green_steps), 1)
        self.assertEqual(green_steps[0].duration, 240.0)
        self.assertEqual(green_steps[0].orange_threshold, 30.0)

    def test_ab_then_cd_share_the_same_end_number(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=1))
        steps = mode.build_sequence()

        end_numbers = {s.end_number for s in steps}
        self.assertEqual(end_numbers, {1})

        turns_in_order = [s.current_turn for s in steps]
        self.assertEqual(turns_in_order, ["A-B", "A-B", "C-D", "C-D"])

    def test_end_number_only_increments_after_both_relays_shot(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2,
                                        alternate_relay_order_each_series=False))
        steps = mode.build_sequence()

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        end1_steps = shooting_steps[:4]
        self.assertTrue(all(s.end_number == 1 for s in end1_steps))
        self.assertEqual([s.current_turn for s in end1_steps], ["A-B", "A-B", "C-D", "C-D"])

        end2_steps = shooting_steps[4:8]
        self.assertTrue(all(s.end_number == 2 for s in end2_steps))

    def test_alternate_relay_order_flips_on_the_second_series(self) -> None:
        cfg = IndoorConfig(series=2, ends_per_series=1, alternate_relay_order_each_series=True)
        steps = IndoorMode(cfg).build_sequence()

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        series1_turns = [s.current_turn for s in shooting_steps if s.unit_number == 1]
        series2_turns = [s.current_turn for s in shooting_steps if s.unit_number == 2]
        self.assertEqual(series1_turns, ["A-B", "A-B", "C-D", "C-D"])
        self.assertEqual(series2_turns, ["C-D", "C-D", "A-B", "A-B"])

    def test_alternation_disabled_keeps_the_same_order_every_series(self) -> None:
        cfg = IndoorConfig(series=2, ends_per_series=1, alternate_relay_order_each_series=False)
        steps = IndoorMode(cfg).build_sequence()

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        series1_turns = [s.current_turn for s in shooting_steps if s.unit_number == 1]
        series2_turns = [s.current_turn for s in shooting_steps if s.unit_number == 2]
        self.assertEqual(series1_turns, series2_turns)

    def test_cd_then_ab_as_the_base_order(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="cd_then_ab")
        steps = IndoorMode(cfg).build_sequence()
        self.assertEqual([s.current_turn for s in steps], ["C-D", "C-D", "A-B", "A-B"])

    def test_ab_only_never_shows_cd(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2, turn_mode="ab_only"))
        steps = mode.build_sequence()
        self.assertTrue(all(s.current_turn == "A-B" for s in steps))
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        self.assertEqual(len(shooting_steps), 2 * 2)

    def test_cd_only_never_shows_ab(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2, turn_mode="cd_only"))
        steps = mode.build_sequence()
        self.assertTrue(all(s.current_turn == "C-D" for s in steps))

    def test_alternation_has_no_effect_on_single_relay_modes(self) -> None:
        cfg = IndoorConfig(series=2, ends_per_series=1, turn_mode="ab_only",
                            alternate_relay_order_each_series=True)
        steps = IndoorMode(cfg).build_sequence()
        self.assertTrue(all(s.current_turn == "A-B" for s in steps))

    def test_invalid_turn_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndoorConfig(turn_mode="something_else")

    def test_shoot_time_and_orange_threshold_are_configurable(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="ab_only",
                            prep_time=10, shoot_time=90, orange_warning_time=20)
        steps = IndoorMode(cfg).build_sequence()

        self.assertEqual([s.phase for s in steps], [Phase.RED, Phase.GREEN])
        self.assertEqual([s.duration for s in steps], [10, 90])
        self.assertEqual(steps[1].orange_threshold, 20)

    def test_zero_prep_time_is_skipped(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="ab_only", prep_time=0)
        steps = IndoorMode(cfg).build_sequence()
        self.assertNotIn(Phase.RED, [s.phase for s in steps])

    def test_zero_orange_warning_disables_the_threshold(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="ab_only",
                            orange_warning_time=0)
        steps = IndoorMode(cfg).build_sequence()
        green_step = next(s for s in steps if s.phase == Phase.GREEN)
        self.assertIsNone(green_step.orange_threshold)

    def test_invalid_config_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndoorConfig(series=0)
        with self.assertRaises(ValueError):
            IndoorConfig(shoot_time=-1)
        with self.assertRaises(ValueError):
            IndoorConfig(orange_warning_time=300, shoot_time=240)  # threshold > total

    def test_pause_inserted_between_ends_but_not_after_the_last(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=3, turn_mode="ab_only"))
        steps = mode.build_sequence()

        pause_steps = [s for s in steps if s.phase == Phase.PAUSE]
        self.assertEqual(len(pause_steps), 2)
        self.assertEqual(steps[-1].phase, Phase.GREEN)  # sequence ends on shooting, not pause

    def test_pause_step_previews_the_next_end(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2,
                                        alternate_relay_order_each_series=False))
        steps = mode.build_sequence()

        pause_step = next(s for s in steps if s.phase == Phase.PAUSE)
        self.assertEqual(pause_step.end_number, 2)
        self.assertEqual(pause_step.unit_number, 1)
        self.assertEqual(pause_step.current_turn, "A-B")
        self.assertIsNone(pause_step.duration)

    def test_pause_preview_reflects_the_flipped_order_across_series(self) -> None:
        cfg = IndoorConfig(series=2, ends_per_series=1, alternate_relay_order_each_series=True)
        steps = IndoorMode(cfg).build_sequence()

        pause_step = next(s for s in steps if s.phase == Phase.PAUSE)
        self.assertEqual(pause_step.unit_number, 2)
        self.assertEqual(pause_step.end_number, 1)
        self.assertEqual(pause_step.current_turn, "C-D")

    def test_pause_shows_the_distance_of_the_upcoming_volee(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2))
        steps = mode.build_sequence()
        pause_step = next(s for s in steps if s.phase == Phase.PAUSE)
        self.assertEqual(pause_step.distance_label, "20 yards")

    def test_default_shoot_time_is_four_minutes_per_ifaa_rule(self) -> None:
        cfg = IndoorConfig()
        self.assertEqual(cfg.shoot_time, 240.0)  # règle IFAA : 4 min/volée
        self.assertEqual(cfg.orange_warning_time, 30.0)

    def test_default_prep_time_matches_the_corrected_club_value(self) -> None:
        cfg = IndoorConfig()
        self.assertEqual(cfg.prep_time, 10.0)

    def test_default_distance_and_arrows_match_ifaa_rule(self) -> None:
        cfg = IndoorConfig()
        self.assertEqual(cfg.distance_label, "20 yards")
        self.assertEqual(cfg.arrows_per_end, 5)
        self.assertEqual(cfg.ends_per_series, 6)
        self.assertEqual(cfg.series, 2)


if __name__ == "__main__":
    unittest.main()

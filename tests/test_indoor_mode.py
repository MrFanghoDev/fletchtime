import unittest

from fletchtime_engine import IndoorConfig, IndoorMode, Phase


class TestIndoorMode(unittest.TestCase):
    def test_default_config_matches_club_competition(self) -> None:
        """2 séries de 6 volées de 5 flèches : série 1 en A-B puis C-D,
        série 2 en C-D puis A-B (alternance activée par défaut)."""
        mode = IndoorMode()
        steps = mode.build_sequence()

        total_ends = 2 * 6
        self.assertEqual(len(steps), total_ends * 6 + (total_ends - 1))

        end_numbers = sorted({s.end_number for s in steps})
        self.assertEqual(end_numbers, list(range(1, total_ends + 1)))

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        end1_turns = [s.current_turn for s in shooting_steps if s.end_number == 1]
        self.assertEqual(end1_turns, ["A-B", "A-B", "A-B", "C-D", "C-D", "C-D"])

        end7_turns = [s.current_turn for s in shooting_steps if s.end_number == 7]
        self.assertEqual(end7_turns, ["C-D", "C-D", "C-D", "A-B", "A-B", "A-B"])

    def test_ab_then_cd_share_the_same_end_number(self) -> None:
        """Le point central du premier correctif : A-B puis C-D tirent la
        même volée, le numéro ne doit pas changer entre les deux relais."""
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=1))
        steps = mode.build_sequence()

        end_numbers = {s.end_number for s in steps}
        self.assertEqual(end_numbers, {1})  # une seule volée, malgré 2 relais

        turns_in_order = [s.current_turn for s in steps]
        self.assertEqual(turns_in_order, ["A-B", "A-B", "A-B", "C-D", "C-D", "C-D"])

    def test_end_number_only_increments_after_both_relays_shot(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2,
                                        alternate_relay_order_each_series=False))
        steps = mode.build_sequence()

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        end1_steps = shooting_steps[:6]
        self.assertTrue(all(s.end_number == 1 for s in end1_steps))
        self.assertEqual([s.current_turn for s in end1_steps],
                          ["A-B", "A-B", "A-B", "C-D", "C-D", "C-D"])

        end2_steps = shooting_steps[6:12]
        self.assertTrue(all(s.end_number == 2 for s in end2_steps))

    def test_alternate_relay_order_flips_on_the_second_series(self) -> None:
        cfg = IndoorConfig(series=2, ends_per_series=1, alternate_relay_order_each_series=True)
        steps = IndoorMode(cfg).build_sequence()

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        end1_turns = [s.current_turn for s in shooting_steps if s.end_number == 1]
        end2_turns = [s.current_turn for s in shooting_steps if s.end_number == 2]
        self.assertEqual(end1_turns, ["A-B", "A-B", "A-B", "C-D", "C-D", "C-D"])
        self.assertEqual(end2_turns, ["C-D", "C-D", "C-D", "A-B", "A-B", "A-B"])

    def test_alternation_disabled_keeps_the_same_order_every_series(self) -> None:
        cfg = IndoorConfig(series=2, ends_per_series=1, alternate_relay_order_each_series=False)
        steps = IndoorMode(cfg).build_sequence()

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        end1_turns = [s.current_turn for s in shooting_steps if s.end_number == 1]
        end2_turns = [s.current_turn for s in shooting_steps if s.end_number == 2]
        self.assertEqual(end1_turns, end2_turns)  # no flip -- same order both times

    def test_cd_then_ab_as_the_base_order(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="cd_then_ab")
        steps = IndoorMode(cfg).build_sequence()
        self.assertEqual([s.current_turn for s in steps],
                          ["C-D", "C-D", "C-D", "A-B", "A-B", "A-B"])

    def test_ab_only_never_shows_cd(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2, turn_mode="ab_only"))
        steps = mode.build_sequence()
        self.assertTrue(all(s.current_turn == "A-B" for s in steps))
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        self.assertEqual(len(shooting_steps), 2 * 3)

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

    def test_green_then_orange_durations(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="ab_only",
                            prep_time=10, green_time=90, orange_time=30)
        steps = IndoorMode(cfg).build_sequence()

        self.assertEqual([s.phase for s in steps], [Phase.RED, Phase.GREEN, Phase.ORANGE])
        self.assertEqual([s.duration for s in steps], [10, 90, 30])

    def test_zero_prep_time_is_skipped(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, turn_mode="ab_only", prep_time=0)
        steps = IndoorMode(cfg).build_sequence()
        self.assertNotIn(Phase.RED, [s.phase for s in steps])

    def test_invalid_config_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndoorConfig(series=0)
        with self.assertRaises(ValueError):
            IndoorConfig(green_time=-1)

    def test_pause_inserted_between_ends_but_not_after_the_last(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=3, turn_mode="ab_only"))
        steps = mode.build_sequence()

        pause_steps = [s for s in steps if s.phase == Phase.PAUSE]
        self.assertEqual(len(pause_steps), 2)  # between end1->2 and end2->3, not after end3
        self.assertEqual(steps[-1].phase, Phase.ORANGE)  # sequence ends on shooting, not pause

    def test_pause_step_previews_the_next_end(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2,
                                        alternate_relay_order_each_series=False))
        steps = mode.build_sequence()

        pause_step = next(s for s in steps if s.phase == Phase.PAUSE)
        self.assertEqual(pause_step.end_number, 2)
        self.assertEqual(pause_step.current_turn, "A-B")  # end 2 starts with A-B again
        self.assertIsNone(pause_step.duration)

    def test_pause_preview_reflects_the_flipped_order_across_series(self) -> None:
        cfg = IndoorConfig(series=2, ends_per_series=1, alternate_relay_order_each_series=True)
        steps = IndoorMode(cfg).build_sequence()

        pause_step = next(s for s in steps if s.phase == Phase.PAUSE)
        self.assertEqual(pause_step.end_number, 2)
        self.assertEqual(pause_step.current_turn, "C-D")  # end 2 (series 2) starts with C-D


if __name__ == "__main__":
    unittest.main()

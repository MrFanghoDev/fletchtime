import unittest

from fletchtime_engine import IndoorConfig, IndoorMode, Phase


class TestIndoorMode(unittest.TestCase):
    def test_default_config_matches_club_competition(self) -> None:
        """2 séries de 6 volées de 5 flèches, comme au concours du club."""
        mode = IndoorMode()
        steps = mode.build_sequence()

        total_ends = 2 * 6
        # each end = 2 relais (A-B, C-D) x (RED+GREEN+ORANGE) = 6 steps,
        # plus une PAUSE après chaque volée sauf la dernière.
        self.assertEqual(len(steps), total_ends * 6 + (total_ends - 1))

        end_numbers = sorted({s.end_number for s in steps})
        self.assertEqual(end_numbers, list(range(1, total_ends + 1)))

    def test_ab_then_cd_share_the_same_end_number(self) -> None:
        """Le point central du correctif : A-B puis C-D tirent la même
        volée, le numéro ne doit pas changer entre les deux relais."""
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=1))
        steps = mode.build_sequence()

        end_numbers = {s.end_number for s in steps}
        self.assertEqual(end_numbers, {1})  # une seule volée, malgré 2 relais

        turns_in_order = [s.current_turn for s in steps]
        self.assertEqual(turns_in_order, ["A-B", "A-B", "A-B", "C-D", "C-D", "C-D"])

    def test_end_number_only_increments_after_both_relays_shot(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2))
        steps = mode.build_sequence()

        # les 6 premiers steps de tir (hors pause) sont la volée 1 (A-B puis C-D)
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        end1_steps = shooting_steps[:6]
        self.assertTrue(all(s.end_number == 1 for s in end1_steps))
        self.assertEqual([s.current_turn for s in end1_steps],
                          ["A-B", "A-B", "A-B", "C-D", "C-D", "C-D"])

        end2_steps = shooting_steps[6:12]
        self.assertTrue(all(s.end_number == 2 for s in end2_steps))

    def test_ab_only_never_shows_cd(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2, turn_mode="ab_only"))
        steps = mode.build_sequence()
        self.assertTrue(all(s.current_turn == "A-B" for s in steps))
        # un seul relais par volée = 3 steps de tir (pas 6)
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        self.assertEqual(len(shooting_steps), 2 * 3)

    def test_cd_only_never_shows_ab(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2, turn_mode="cd_only"))
        steps = mode.build_sequence()
        self.assertTrue(all(s.current_turn == "C-D" for s in steps))

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
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2))
        steps = mode.build_sequence()

        pause_step = next(s for s in steps if s.phase == Phase.PAUSE)
        self.assertEqual(pause_step.end_number, 2)
        self.assertEqual(pause_step.current_turn, "A-B")  # end 2 starts with A-B again
        self.assertIsNone(pause_step.duration)


if __name__ == "__main__":
    unittest.main()

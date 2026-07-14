import unittest

from fletchtime_engine import IndoorConfig, IndoorMode, Phase


class TestIndoorMode(unittest.TestCase):
    def test_default_config_matches_club_competition(self) -> None:
        """2 séries de 6 volées de 5 flèches, comme au concours du club."""
        mode = IndoorMode()
        steps = mode.build_sequence()

        total_ends = 2 * 6
        # each end = RED + GREEN + ORANGE, plus a PAUSE step after every end
        # except the very last one (nothing to wait for once it's over).
        self.assertEqual(len(steps), total_ends * 3 + (total_ends - 1))

        end_numbers = sorted({s.end_number for s in steps})
        self.assertEqual(end_numbers, list(range(1, total_ends + 1)))

    def test_pause_inserted_between_ends_but_not_after_the_last(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=3))
        steps = mode.build_sequence()

        pause_steps = [s for s in steps if s.phase == Phase.PAUSE]
        self.assertEqual(len(pause_steps), 2)  # between end1->2 and end2->3, not after end3
        self.assertEqual(steps[-1].phase, Phase.ORANGE)  # sequence ends on shooting, not pause

    def test_pause_step_previews_the_next_end(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=2, rotate_turn=True))
        steps = mode.build_sequence()

        pause_step = next(s for s in steps if s.phase == Phase.PAUSE)
        self.assertEqual(pause_step.end_number, 2)
        self.assertEqual(pause_step.current_turn, "C-D")  # end 2's turn, previewed
        self.assertIsNone(pause_step.duration)

    def test_turn_rotates_ab_cd_each_end(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=4, rotate_turn=True))
        steps = mode.build_sequence()

        turns_by_end = {s.end_number: s.current_turn for s in steps}
        self.assertEqual(turns_by_end[1], "A-B")
        self.assertEqual(turns_by_end[2], "C-D")
        self.assertEqual(turns_by_end[3], "A-B")
        self.assertEqual(turns_by_end[4], "C-D")

    def test_turn_fixed_when_rotation_disabled(self) -> None:
        mode = IndoorMode(IndoorConfig(series=1, ends_per_series=3, rotate_turn=False))
        steps = mode.build_sequence()
        self.assertTrue(all(s.current_turn == "" for s in steps))

    def test_green_then_orange_durations(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, prep_time=10,
                            green_time=90, orange_time=30)
        steps = IndoorMode(cfg).build_sequence()

        self.assertEqual([s.phase for s in steps], [Phase.RED, Phase.GREEN, Phase.ORANGE])
        self.assertEqual([s.duration for s in steps], [10, 90, 30])

    def test_zero_prep_time_is_skipped(self) -> None:
        cfg = IndoorConfig(series=1, ends_per_series=1, prep_time=0)
        steps = IndoorMode(cfg).build_sequence()
        self.assertNotIn(Phase.RED, [s.phase for s in steps])

    def test_invalid_config_raises(self) -> None:
        with self.assertRaises(ValueError):
            IndoorConfig(series=0)
        with self.assertRaises(ValueError):
            IndoorConfig(green_time=-1)


if __name__ == "__main__":
    unittest.main()

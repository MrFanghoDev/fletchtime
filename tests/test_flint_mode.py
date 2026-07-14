import unittest

from fletchtime_engine import FlintConfig, FlintMode, Phase


class TestFlintMode(unittest.TestCase):
    def test_default_config_is_one_parcours(self) -> None:
        """1 Flint du concours du club = 2 unités standards (1 parcours)."""
        mode = FlintMode()
        steps = mode.build_sequence()

        unit_numbers = sorted({s.unit_number for s in steps})
        self.assertEqual(unit_numbers, [1, 2])

    def test_standard_distance_order_matches_the_real_shooting_lines(self) -> None:
        """Ordre réel des lignes de tir (3,1,5,4,6,2), pas un ordre croissant."""
        mode = FlintMode(FlintConfig(units=1, turn_mode="ab_only"))
        steps = mode.build_sequence()

        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]
        distances_by_end = {}
        for s in shooting_steps:
            if s.end_number <= 6:
                distances_by_end.setdefault(s.end_number, s.distance_label)

        self.assertEqual(distances_by_end, {
            1: "25 yards", 2: "20 pieds", 3: "30 yards",
            4: "15 yards", 5: "20 yards", 6: "10 yards",
        })

    def test_standard_end_has_correct_phases(self) -> None:
        mode = FlintMode(FlintConfig(units=1, turn_mode="ab_only"))
        steps = mode.build_sequence()

        end1 = [s for s in steps if s.unit_number == 1 and s.end_number == 1
                and s.phase != Phase.PAUSE]
        self.assertEqual([s.phase for s in end1], [Phase.RED, Phase.GREEN, Phase.ORANGE])
        self.assertTrue(all(s.distance_label == "25 yards" for s in end1))
        self.assertTrue(all(s.arrow_in_end == 0 for s in end1))  # not a walk-up

    def test_walkup_end_has_45_seconds_per_arrow_and_4_distances(self) -> None:
        mode = FlintMode(FlintConfig(units=1, turn_mode="ab_only"))
        steps = mode.build_sequence()
        walkup_steps = [s for s in steps if s.unit_number == 1 and s.end_number == 7]

        green_steps = [s for s in walkup_steps if s.phase == Phase.GREEN]
        self.assertEqual(len(green_steps), 4)
        self.assertTrue(all(s.duration == 45.0 for s in green_steps))

        distances_in_order = [s.distance_label for s in green_steps]
        self.assertEqual(distances_in_order, ["30 yards", "25 yards", "20 yards", "15 yards"])

        arrow_numbers = [s.arrow_in_end for s in green_steps]
        self.assertEqual(arrow_numbers, [1, 2, 3, 4])

    def test_walkup_advances_together_between_arrows(self) -> None:
        mode = FlintMode(FlintConfig(units=1, turn_mode="ab_only"))
        steps = mode.build_sequence()
        walkup_steps = [s for s in steps if s.end_number == 7]
        if walkup_steps[0].phase == Phase.PAUSE:
            walkup_steps = walkup_steps[1:]
        self.assertEqual([s.phase for s in walkup_steps], [Phase.RED, Phase.GREEN] * 4)

    def test_mismatched_standard_distances_raises(self) -> None:
        with self.assertRaises(ValueError):
            FlintConfig(standard_ends_per_unit=6, standard_distances=["a", "b"])

    def test_mismatched_walkup_distances_raises(self) -> None:
        with self.assertRaises(ValueError):
            FlintConfig(walkup_arrows=4, walkup_distances=["a", "b"])

    def test_invalid_turn_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            FlintConfig(turn_mode="bogus")

    # -- relay structure: each relay shoots the WHOLE unit, not per-end --

    def test_ab_then_cd_each_shoots_the_entire_unit_before_the_other(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_then_cd")
        steps = FlintMode(cfg).build_sequence()
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]

        turns_in_order = [s.current_turn for s in shooting_steps]
        # first half of the (doubled) sequence is entirely A-B, second half entirely C-D
        half = len(turns_in_order) // 2
        self.assertTrue(all(t == "A-B" for t in turns_in_order[:half]))
        self.assertTrue(all(t == "C-D" for t in turns_in_order[half:]))

    def test_second_relay_repeats_the_same_end_numbers_from_the_start(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_then_cd")
        steps = FlintMode(cfg).build_sequence()
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]

        ab_steps = [s for s in shooting_steps if s.current_turn == "A-B"]
        cd_steps = [s for s in shooting_steps if s.current_turn == "C-D"]

        self.assertEqual(sorted({s.end_number for s in ab_steps}), list(range(1, 8)))
        self.assertEqual(sorted({s.end_number for s in cd_steps}), list(range(1, 8)))
        # same distance for end 1 whichever relay is shooting it
        ab_end1_distance = next(s.distance_label for s in ab_steps if s.end_number == 1)
        cd_end1_distance = next(s.distance_label for s in cd_steps if s.end_number == 1)
        self.assertEqual(ab_end1_distance, cd_end1_distance)

    def test_cd_then_ab_starts_with_cd(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="cd_then_ab")
        steps = FlintMode(cfg).build_sequence()
        self.assertEqual(steps[0].current_turn, "C-D")

    def test_ab_only_never_shows_cd(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        steps = FlintMode(cfg).build_sequence()
        self.assertTrue(all(s.current_turn == "A-B" for s in steps))

    def test_ab_only_does_not_double_the_sequence(self) -> None:
        cfg_single = FlintConfig(units=1, turn_mode="ab_only")
        cfg_double = FlintConfig(units=1, turn_mode="ab_then_cd")
        steps_single = [s for s in FlintMode(cfg_single).build_sequence() if s.phase != Phase.PAUSE]
        steps_double = [s for s in FlintMode(cfg_double).build_sequence() if s.phase != Phase.PAUSE]
        self.assertEqual(len(steps_double), len(steps_single) * 2)

    def test_pause_between_the_two_relay_passes_of_the_same_unit(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_then_cd")
        steps = FlintMode(cfg).build_sequence()

        # find the pause right after A-B's last walk-up arrow
        for i, s in enumerate(steps):
            if s.phase == Phase.PAUSE and s.current_turn == "C-D" and s.end_number == 1:
                pause_step = s
                break
        else:
            self.fail("expected a pause previewing C-D's pass through the unit")
        self.assertIsNone(pause_step.duration)

    def test_units_default_to_two_for_one_parcours(self) -> None:
        cfg = FlintConfig(units=1)
        steps = FlintMode(cfg).build_sequence()
        self.assertEqual(sorted({s.unit_number for s in steps}), [1])

    def test_no_pause_after_the_very_last_step_of_the_match(self) -> None:
        cfg = FlintConfig(units=2, turn_mode="ab_then_cd")
        steps = FlintMode(cfg).build_sequence()
        self.assertEqual(steps[-1].phase, Phase.GREEN)  # last walk-up arrow, not a pause


if __name__ == "__main__":
    unittest.main()

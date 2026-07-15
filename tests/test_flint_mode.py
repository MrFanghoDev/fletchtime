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
        self.assertEqual([s.phase for s in end1], [Phase.RED, Phase.GREEN])
        self.assertTrue(all(s.distance_label == "25 yards" for s in end1))
        self.assertTrue(all(s.arrow_in_end == 0 for s in end1))  # not a walk-up

    def test_standard_target_image_alternates_by_end_parity(self) -> None:
        """Volées 1,3,5 -> blason 1 spot ; volées 2,4,6 -> blason 4 spots."""
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        steps = FlintMode(cfg).build_sequence()
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]

        by_end = {}
        for s in shooting_steps:
            if s.end_number <= 6:
                by_end.setdefault(s.end_number, s.target_image)

        self.assertEqual(by_end[1], cfg.standard_target_image_1spot)
        self.assertEqual(by_end[2], cfg.standard_target_image_4spot)
        self.assertEqual(by_end[3], cfg.standard_target_image_1spot)
        self.assertEqual(by_end[4], cfg.standard_target_image_4spot)
        self.assertEqual(by_end[5], cfg.standard_target_image_1spot)
        self.assertEqual(by_end[6], cfg.standard_target_image_4spot)

    def test_walkup_arrows_switch_to_orange_in_the_last_10_seconds(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        steps = FlintMode(cfg).build_sequence()
        walkup_green_steps = [
            s for s in steps if s.end_number == 7 and s.phase == Phase.GREEN
        ]
        self.assertEqual(len(walkup_green_steps), 4)
        self.assertTrue(all(s.orange_threshold == 10.0 for s in walkup_green_steps))
        self.assertTrue(all(s.orange_sound_event == "warning_orange" for s in walkup_green_steps))

    def test_walkup_end_uses_the_1spot_target(self) -> None:
        cfg = FlintConfig(units=1, turn_mode="ab_only")
        steps = FlintMode(cfg).build_sequence()
        walkup_steps = [s for s in steps if s.end_number == 7 and s.phase == Phase.GREEN]
        self.assertTrue(all(s.target_image == cfg.walkup_target_image for s in walkup_steps))

    def test_standard_shoot_time_is_continuous_180s_with_20s_orange(self) -> None:
        cfg = FlintConfig()
        self.assertEqual(cfg.standard_shoot_time, 180.0)
        self.assertEqual(cfg.standard_orange_warning_time, 20.0)

        steps = FlintMode(cfg).build_sequence()
        green_step = next(s for s in steps if s.phase == Phase.GREEN and s.arrow_in_end == 0)
        self.assertEqual(green_step.duration, 180.0)
        self.assertEqual(green_step.orange_threshold, 20.0)

    def test_prep_times_match_the_corrected_club_values(self) -> None:
        cfg = FlintConfig()
        self.assertEqual(cfg.standard_prep_time, 10.0)
        self.assertEqual(cfg.walkup_prep_time, 10.0)  # "inter-temps" entre flèches du walk-up

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

    def test_alternate_relay_order_flips_on_the_second_unit(self) -> None:
        """Séquence réelle du club : unité 1 = A-B puis C-D, unité 2 =
        C-D puis A-B (alternance activée par défaut)."""
        cfg = FlintConfig(units=2, turn_mode="ab_then_cd")
        steps = FlintMode(cfg).build_sequence()
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]

        unit1_turns_in_order = [s.current_turn for s in shooting_steps if s.unit_number == 1]
        unit2_turns_in_order = [s.current_turn for s in shooting_steps if s.unit_number == 2]

        half1 = len(unit1_turns_in_order) // 2
        half2 = len(unit2_turns_in_order) // 2
        self.assertTrue(all(t == "A-B" for t in unit1_turns_in_order[:half1]))
        self.assertTrue(all(t == "C-D" for t in unit1_turns_in_order[half1:]))
        self.assertTrue(all(t == "C-D" for t in unit2_turns_in_order[:half2]))
        self.assertTrue(all(t == "A-B" for t in unit2_turns_in_order[half2:]))

    def test_alternation_disabled_keeps_the_same_order_every_unit(self) -> None:
        cfg = FlintConfig(units=2, turn_mode="ab_then_cd",
                           alternate_relay_order_each_unit=False)
        steps = FlintMode(cfg).build_sequence()
        shooting_steps = [s for s in steps if s.phase != Phase.PAUSE]

        unit1_turns = [s.current_turn for s in shooting_steps if s.unit_number == 1]
        unit2_turns = [s.current_turn for s in shooting_steps if s.unit_number == 2]
        self.assertEqual(unit1_turns, unit2_turns)  # no flip

    def test_alternation_has_no_effect_on_single_relay_modes(self) -> None:
        cfg = FlintConfig(units=2, turn_mode="ab_only", alternate_relay_order_each_unit=True)
        steps = FlintMode(cfg).build_sequence()
        self.assertTrue(all(s.current_turn == "A-B" for s in steps))

    def test_pause_between_units_shows_the_flipped_relay_and_first_distance(self) -> None:
        cfg = FlintConfig(units=2, turn_mode="ab_then_cd")
        steps = FlintMode(cfg).build_sequence()

        pause_before_unit2 = next(
            s for s in steps if s.phase == Phase.PAUSE and s.unit_number == 2
        )
        self.assertEqual(pause_before_unit2.current_turn, "C-D")  # unit 2 starts with C-D
        self.assertEqual(pause_before_unit2.end_number, 1)
        self.assertEqual(pause_before_unit2.distance_label, "25 yards")  # end 1's distance

    def test_pause_between_relays_shows_the_upcoming_distance(self) -> None:
        """La distance affichée pendant le ramassage des flèches est déjà
        celle de la prochaine volée -- y compris au changement de relais."""
        cfg = FlintConfig(units=1, turn_mode="ab_then_cd")
        steps = FlintMode(cfg).build_sequence()

        pause_before_cd = next(
            s for s in steps if s.phase == Phase.PAUSE and s.current_turn == "C-D"
            and s.end_number == 1
        )
        self.assertEqual(pause_before_cd.distance_label, "25 yards")


if __name__ == "__main__":
    unittest.main()

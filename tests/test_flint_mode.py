import unittest

from fletchtime_engine import FlintConfig, FlintMode, Phase


class TestFlintMode(unittest.TestCase):
    def test_default_config_is_one_parcours(self) -> None:
        """1 Flint du concours du club = 2 unités standards (1 parcours)."""
        mode = FlintMode()
        steps = mode.build_sequence()

        unit_numbers = sorted({s.unit_number for s in steps})
        self.assertEqual(unit_numbers, [1, 2])

    def test_standard_end_has_correct_distance_and_phases(self) -> None:
        mode = FlintMode()
        steps = mode.build_sequence()

        unit1_end1 = [s for s in steps if s.unit_number == 1 and s.end_number == 1]
        self.assertEqual([s.phase for s in unit1_end1], [Phase.RED, Phase.GREEN, Phase.ORANGE])
        self.assertTrue(all(s.distance_label == "20 pieds" for s in unit1_end1))
        # standard ends are single-distance, not part of a walk-up
        self.assertTrue(all(s.arrow_in_end == 0 for s in unit1_end1))

    def test_six_standard_ends_then_one_walkup_end_per_unit(self) -> None:
        mode = FlintMode()
        steps = mode.build_sequence()
        unit1_steps = [s for s in steps if s.unit_number == 1]

        end_numbers = sorted({s.end_number for s in unit1_steps})
        # 6 standard ends + 1 walk-up end, numbered 1..7
        self.assertEqual(end_numbers, list(range(1, 8)))

        walkup_steps = [s for s in unit1_steps if s.end_number == 7]
        # 4 arrows x (RED prep + GREEN shoot) = 8 steps
        self.assertEqual(len(walkup_steps), 8)

    def test_walkup_end_has_45_seconds_per_arrow_and_4_distances(self) -> None:
        mode = FlintMode()
        steps = mode.build_sequence()
        walkup_steps = [s for s in steps if s.unit_number == 1 and s.end_number == 7]

        green_steps = [s for s in walkup_steps if s.phase == Phase.GREEN]
        self.assertEqual(len(green_steps), 4)
        self.assertTrue(all(s.duration == 45.0 for s in green_steps))

        distances_in_order = [s.distance_label for s in green_steps]
        self.assertEqual(distances_in_order, ["30 yards", "25 yards", "20 yards", "15 yards"])

        arrow_numbers = [s.arrow_in_end for s in green_steps]
        self.assertEqual(arrow_numbers, [1, 2, 3, 4])
        self.assertTrue(all(s.total_arrows_in_end == 4 for s in green_steps))

    def test_walkup_advances_together_between_arrows(self) -> None:
        """Chaque flèche du walk-up est un step GREEN indépendant : le DOS
        (ou l'engine en mode automatique) enchaîne les 4 sans revenir en
        arrière, ce qui correspond à 'tout le monde avance pour la flèche
        suivante'."""
        mode = FlintMode()
        steps = mode.build_sequence()
        walkup_steps = [s for s in steps if s.unit_number == 1 and s.end_number == 7]

        phases_in_order = [s.phase for s in walkup_steps]
        self.assertEqual(
            phases_in_order,
            [Phase.RED, Phase.GREEN] * 4,
        )

    def test_units_default_to_two_for_one_parcours(self) -> None:
        cfg = FlintConfig(units=1)
        steps = FlintMode(cfg).build_sequence()
        self.assertEqual(sorted({s.unit_number for s in steps}), [1])

    def test_mismatched_standard_distances_raises(self) -> None:
        with self.assertRaises(ValueError):
            FlintConfig(standard_ends_per_unit=6, standard_distances=["a", "b"])

    def test_mismatched_walkup_distances_raises(self) -> None:
        with self.assertRaises(ValueError):
            FlintConfig(walkup_arrows=4, walkup_distances=["a", "b"])


if __name__ == "__main__":
    unittest.main()

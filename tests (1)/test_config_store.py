import tempfile
import unittest
from pathlib import Path

from fletchtime.server import config_store


class TestConfigStore(unittest.TestCase):
    def setUp(self) -> None:
        # Isole chaque test dans un dossier temporaire : ne jamais toucher
        # aux vrais fichiers config/*.toml du dépôt pendant les tests.
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_indoor = config_store.INDOOR_TOML
        self._original_flint = config_store.FLINT_TOML
        self._original_app = config_store.APP_TOML
        self._original_auth = config_store.AUTH_TOML
        config_store.INDOOR_TOML = Path(self._tmpdir.name) / "indoor.toml"
        config_store.FLINT_TOML = Path(self._tmpdir.name) / "flint.toml"
        config_store.APP_TOML = Path(self._tmpdir.name) / "app.toml"
        config_store.AUTH_TOML = Path(self._tmpdir.name) / "auth.toml"

    def tearDown(self) -> None:
        config_store.INDOOR_TOML = self._original_indoor
        config_store.FLINT_TOML = self._original_flint
        config_store.APP_TOML = self._original_app
        config_store.AUTH_TOML = self._original_auth
        self._tmpdir.cleanup()

    def test_missing_file_falls_back_to_dataclass_defaults(self) -> None:
        cfg = config_store.load_indoor_config()
        self.assertEqual(cfg.shoot_time, 240.0)
        self.assertEqual(cfg.turn_mode, "ab_then_cd")

    def test_save_then_load_round_trips_correctly(self) -> None:
        config_store.save_indoor_config({"shoot_time": 200.0, "orange_warning_time": 25.0})
        cfg = config_store.load_indoor_config()
        self.assertEqual(cfg.shoot_time, 200.0)
        self.assertEqual(cfg.orange_warning_time, 25.0)
        # les champs non fournis gardent leur défaut normal
        self.assertEqual(cfg.series, 2)

    def test_saved_file_is_actually_written_to_disk(self) -> None:
        config_store.save_indoor_config({"shoot_time": 199.0})
        self.assertTrue(config_store.INDOOR_TOML.exists())
        content = config_store.INDOOR_TOML.read_text(encoding="utf-8")
        self.assertIn("shoot_time = 199.0", content)

    def test_invalid_override_raises_and_does_not_write_the_file(self) -> None:
        with self.assertRaises(ValueError):
            # seuil orange > temps de tir total -- invalide selon IndoorConfig
            config_store.save_indoor_config({"shoot_time": 100.0, "orange_warning_time": 999.0})
        self.assertFalse(config_store.INDOOR_TOML.exists())

    def test_unknown_key_in_file_is_ignored_not_fatal(self) -> None:
        config_store.INDOOR_TOML.parent.mkdir(parents=True, exist_ok=True)
        config_store.INDOOR_TOML.write_text(
            'shoot_time = 210.0\nsome_unknown_field = "whatever"\n', encoding="utf-8"
        )
        cfg = config_store.load_indoor_config()
        self.assertEqual(cfg.shoot_time, 210.0)

    def test_flint_distances_round_trip_as_lists(self) -> None:
        custom = ["1 yard", "2 yards", "3 yards", "4 yards", "5 yards", "6 yards"]
        config_store.save_flint_config({"standard_distances": custom})
        cfg = config_store.load_flint_config()
        self.assertEqual(cfg.standard_distances, custom)

    def test_flint_missing_file_falls_back_to_defaults(self) -> None:
        cfg = config_store.load_flint_config()
        self.assertEqual(cfg.units, 2)
        self.assertEqual(cfg.walkup_time_per_arrow, 45.0)

    def test_comments_are_written_for_known_fields(self) -> None:
        config_store.save_indoor_config({})
        content = config_store.INDOOR_TOML.read_text(encoding="utf-8")
        self.assertIn("# Temps de tir total, décompte continu (secondes)", content)

    def test_app_config_defaults_to_classic_pack(self) -> None:
        app = config_store.load_app_config()
        self.assertEqual(app["sound_pack"], "classic")

    def test_app_config_default_countdown_tick_seconds_is_5(self) -> None:
        app = config_store.load_app_config()
        self.assertEqual(app["countdown_tick_seconds"], 5)

    def test_app_config_countdown_tick_seconds_save_and_reload(self) -> None:
        config_store.save_app_config({"countdown_tick_seconds": 8})
        app = config_store.load_app_config()
        self.assertEqual(app["countdown_tick_seconds"], 8)

    def test_app_config_negative_countdown_tick_seconds_raises(self) -> None:
        with self.assertRaises(ValueError):
            config_store.save_app_config({"countdown_tick_seconds": -1})

    def test_auth_config_default_password_is_empty(self) -> None:
        self.assertEqual(config_store.load_auth_config()["password"], "")

    def test_auth_config_save_and_reload(self) -> None:
        config_store.save_auth_config({"password": "secret"})
        self.assertEqual(config_store.load_auth_config()["password"], "secret")

    def test_auth_config_can_be_cleared_back_to_empty(self) -> None:
        config_store.save_auth_config({"password": "secret"})
        config_store.save_auth_config({"password": ""})
        self.assertEqual(config_store.load_auth_config()["password"], "")

    def test_app_config_save_and_reload(self) -> None:
        config_store.save_app_config({"sound_pack": "mon_club"})
        app = config_store.load_app_config()
        self.assertEqual(app["sound_pack"], "mon_club")

    def test_app_config_unknown_key_is_ignored(self) -> None:
        config_store.save_app_config({"sound_pack": "classic", "bogus_field": "x"})
        app = config_store.load_app_config()
        self.assertNotIn("bogus_field", app)


if __name__ == "__main__":
    unittest.main()

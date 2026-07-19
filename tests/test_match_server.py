import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from fletchtime.server import config_store, match_server
from fletchtime.server.match_server import MatchServer

# Isole config_store.MATCH_STATE_JSON pour tout ce module de tests, quelle
# que soit la classe -- plusieurs classes construisent un MatchServer()
# sans jamais rediriger les chemins de config_store (voir TestMatchServer
# ci-dessous), donc sans ceci, un instantané laissé par un test
# contaminerait le suivant : MatchServer.__init__ tente une restauration
# automatique dès la construction (voir _try_restore_from_snapshot).
_original_match_state_json = config_store.MATCH_STATE_JSON


def setUpModule() -> None:
    global _match_state_tmpdir
    _match_state_tmpdir = tempfile.TemporaryDirectory()
    config_store.MATCH_STATE_JSON = Path(_match_state_tmpdir.name) / "match_state.json"


def tearDownModule() -> None:
    config_store.MATCH_STATE_JSON = _original_match_state_json
    _match_state_tmpdir.cleanup()


class FakeWebSocket:
    """Stand-in for a real websocket connection: just records what would
    have been sent. Lets us test MatchServer's broadcast logic without
    depending on the ``websockets`` package or a real network socket --
    useful in environments (like this one) where installing it isn't
    guaranteed to be possible.
    """

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)

    def last_state(self) -> dict:
        return json.loads(self.sent[-1])["state"]

    def last_message(self):
        return json.loads(self.sent[-1])["message"]

    def last_language(self):
        return json.loads(self.sent[-1])["language"]

    def last_event_title(self):
        return json.loads(self.sent[-1])["event_title"]

    def last_connected_lanes(self):
        return json.loads(self.sent[-1])["connected_lanes"]

    def last_sound_pack(self):
        return json.loads(self.sent[-1])["sound_pack"]

    def last_config_saved_reply(self):
        for raw in reversed(self.sent):
            parsed = json.loads(raw)
            if parsed.get("type") == "config_saved":
                return parsed
        raise AssertionError("no config_saved reply found")


class TestMatchServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Efface tout instantané laissé par un test précédent -- voir
        # setUpModule/tearDownModule plus haut, qui isole déjà le chemin
        # lui-même, mais pas son contenu entre deux tests de ce fichier.
        config_store.clear_match_snapshot()
        self.server = MatchServer()
        self.control = FakeWebSocket()
        self.display = FakeWebSocket()
        await self.server.register(self.control)
        await self.server.register(self.display)

    async def test_no_match_at_startup(self) -> None:
        self.assertIsNone(self.control.last_state())

    async def test_active_mode_is_none_before_any_match(self) -> None:
        payload = json.loads(self.control.sent[-1])
        self.assertIsNone(payload["active_mode"])

    async def test_active_mode_reflects_the_running_indoor_match(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        payload = json.loads(self.control.sent[-1])
        self.assertEqual(payload["active_mode"], "indoor")

    async def test_active_mode_is_none_after_stop(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "stop"}))
        payload = json.loads(self.control.sent[-1])
        self.assertIsNone(payload["active_mode"])

    async def test_start_flint_broadcasts_first_step_to_all_clients(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_flint"}))
        state = self.display.last_state()
        self.assertEqual(state["phase"], "red")
        self.assertEqual(state["distance_label"], "25 yards")
        # every registered client gets the same broadcast
        self.assertEqual(self.control.last_state(), state)

    async def test_start_flint_accepts_turn_mode(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "start_flint", "turn_mode": "cd_only"})
        )
        self.assertEqual(self.display.last_state()["current_turn"], "C-D")

    async def test_start_flint_alternate_flag_can_be_disabled(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "start_flint",
                    "turn_mode": "ab_then_cd",
                    "alternate": False,
                }
            )
        )
        await self.server.handle_command(
            json.dumps({"action": "goto", "unit": 2, "end": 1, "turn": "A-B"})
        )
        state = self.display.last_state()
        self.assertEqual(state["unit_number"], 2)
        # with alternation off, unit 2 also starts with A-B (no flip to C-D)
        await self.server.handle_command(json.dumps({"action": "next"}))
        self.assertEqual(self.display.last_state()["current_turn"], "A-B")

    async def test_next_advances_and_broadcasts(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_flint"}))
        await self.server.handle_command(json.dumps({"action": "next"}))
        self.assertEqual(self.display.last_state()["phase"], "green")

    async def test_emergency_then_resume_round_trip(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_flint"}))
        await self.server.handle_command(json.dumps({"action": "next"}))  # -> green
        await self.server.handle_command(json.dumps({"action": "emergency"}))
        self.assertEqual(self.display.last_state()["phase"], "emergency")

        await self.server.handle_command(json.dumps({"action": "resume"}))
        self.assertEqual(self.display.last_state()["phase"], "green")

    async def test_message_is_broadcast_and_can_be_cleared(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(
            json.dumps({"action": "message", "value": "Retard 10 min"})
        )
        self.assertEqual(self.display.last_message(), "Retard 10 min")

        await self.server.handle_command(json.dumps({"action": "message", "value": None}))
        self.assertIsNone(self.display.last_message())

    async def test_message_works_even_before_any_match_is_started(self) -> None:
        """Regression test: a message like 'retard de 15 minutes' must be
        showable while state is still None (no engine running yet) --
        this used to be silently dropped."""
        await self.server.handle_command(
            json.dumps({"action": "message", "value": "Début retardé de 15 min"})
        )
        self.assertIsNone(self.display.last_state())
        self.assertEqual(self.display.last_message(), "Début retardé de 15 min")

    async def test_message_persists_across_stop_and_restart(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(
            json.dumps({"action": "message", "value": "Pause déjeuner"})
        )
        await self.server.handle_command(json.dumps({"action": "stop"}))
        self.assertEqual(self.display.last_message(), "Pause déjeuner")

    async def test_default_language_is_french(self) -> None:
        self.assertEqual(self.display.last_language(), "fr")

    async def test_language_can_be_switched_to_english(self) -> None:
        await self.server.handle_command(json.dumps({"action": "set_language", "value": "en"}))
        self.assertEqual(self.display.last_language(), "en")

    async def test_language_persists_across_match_start_and_stop(self) -> None:
        await self.server.handle_command(json.dumps({"action": "set_language", "value": "en"}))
        await self.server.handle_command(json.dumps({"action": "start_flint"}))
        self.assertEqual(self.display.last_language(), "en")
        await self.server.handle_command(json.dumps({"action": "stop"}))
        self.assertEqual(self.display.last_language(), "en")

    async def test_invalid_language_is_ignored_not_fatal(self) -> None:
        await self.server.handle_command(json.dumps({"action": "set_language", "value": "de"}))
        self.assertEqual(self.display.last_language(), "fr")  # unchanged

    async def test_default_event_title_is_none(self) -> None:
        self.assertIsNone(self.display.last_event_title())

    async def test_event_title_can_be_set(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "set_event_title",
                    "value": "Concours FFTL Indoor -- Février 2026",
                }
            )
        )
        self.assertEqual(self.display.last_event_title(), "Concours FFTL Indoor -- Février 2026")

    async def test_event_title_persists_across_match_start_stop_and_restart(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "set_event_title", "value": "Championnat 77"})
        )
        await self.server.handle_command(json.dumps({"action": "start_flint"}))
        self.assertEqual(self.display.last_event_title(), "Championnat 77")
        await self.server.handle_command(json.dumps({"action": "stop"}))
        self.assertEqual(self.display.last_event_title(), "Championnat 77")

    async def test_event_title_can_be_cleared(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "set_event_title", "value": "Championnat 77"})
        )
        await self.server.handle_command(json.dumps({"action": "set_event_title", "value": None}))
        self.assertIsNone(self.display.last_event_title())

    async def test_tick_updates_time_left_and_emits_events(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        self.server.engine.pop_pending_events()  # drain the initial "prep_start"

        # first step is RED(10s); advance the underlying engine directly,
        # the way the real tick_loop would (without sleeping in a test).
        self.server.engine.tick(0.2)
        events = self.server.engine.pop_pending_events()
        await self.server.broadcast_state()

        self.assertEqual(self.display.last_state()["time_left"], 9.8)
        self.assertEqual(events, [])  # no phase transition yet at 0.2s into a 10s step

    async def test_tick_loop_uses_actual_elapsed_time_not_fixed_interval(self) -> None:
        """Régression pour un écart de plusieurs secondes remonté sur
        Windows sur une volée de 45s : tick_loop appelait
        `engine.tick(TICK_INTERVAL)` en supposant que TICK_INTERVAL s'était
        écoulé pile, alors qu'`asyncio.sleep()` ne dort jamais exactement
        la durée demandée -- l'erreur, petite à chaque tick, dérive sur une
        volée longue (plus perceptible sous Windows, dont la granularité
        de l'ordonnanceur est plus grossière que sous Linux). Corrigé en
        mesurant le temps réellement écoulé via `time.monotonic()`."""
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        self.server.engine.pop_pending_events()
        before = self.server.engine.current_state.time_left

        # Chaque appel à time.monotonic() avance un temps simulé d'une
        # valeur fixe DIFFÉRENTE de TICK_INTERVAL (0.2s réel) -- si le
        # code utilisait encore TICK_INTERVAL en dur (l'ancien bug), le
        # décompte serait un multiple de 0.2, jamais de 0.05.
        state = {"t": 1000.0}

        def fake_monotonic():
            state["t"] += 0.05
            return state["t"]

        original_monotonic = match_server.time.monotonic
        match_server.time.monotonic = fake_monotonic
        try:
            task = asyncio.ensure_future(self.server.tick_loop())
            await asyncio.sleep(0.65)  # laisse tourner quelques vrais ticks
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        finally:
            match_server.time.monotonic = original_monotonic

        after = self.server.engine.current_state.time_left
        decrement = before - after
        self.assertGreater(decrement, 0)
        remainder = round(decrement, 10) % 0.05
        self.assertTrue(
            remainder < 1e-6 or abs(remainder - 0.05) < 1e-6,
            f"decrement={decrement} devrait être un multiple de 0.05 (temps mesuré), "
            "pas de 0.2 (TICK_INTERVAL fixe -- signe d'une régression de ce correctif)",
        )

    async def test_unregister_stops_further_broadcasts(self) -> None:
        count_before = len(self.display.sent)
        await self.server.unregister(self.display)
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        self.assertEqual(len(self.display.sent), count_before)  # nothing new after unregister

    async def test_start_indoor_accepts_turn_mode(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "start_indoor", "turn_mode": "cd_only"})
        )
        self.assertEqual(self.display.last_state()["current_turn"], "C-D")

    async def test_start_indoor_alternate_flag_can_be_disabled(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "start_indoor",
                    "turn_mode": "ab_then_cd",
                    "alternate": False,
                }
            )
        )
        # jump straight to série 2, volée 1
        await self.server.handle_command(json.dumps({"action": "goto", "unit": 2, "end": 1}))
        await self.server.handle_command(json.dumps({"action": "next"}))  # leave the preview pause
        # with alternation off, series 2 should still start with A-B (no flip)
        self.assertEqual(self.display.last_state()["current_turn"], "A-B")

    async def test_start_indoor_invalid_turn_mode_is_ignored_not_fatal(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "start_indoor", "turn_mode": "bogus"})
        )
        self.assertIsNone(self.display.last_state())  # no engine created, no crash

    async def test_stop_command_finishes_the_match(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "stop"}))
        self.assertTrue(self.display.last_state()["finished"])

    async def test_restart_command_goes_back_to_the_first_step(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "next"}))
        await self.server.handle_command(json.dumps({"action": "restart"}))
        state = self.display.last_state()
        self.assertEqual(state["phase"], "red")
        self.assertEqual(state["end_number"], 1)

    async def test_goto_command_jumps_to_requested_end(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_flint"}))
        await self.server.handle_command(json.dumps({"action": "goto", "unit": 1, "end": 4}))
        state = self.display.last_state()
        self.assertEqual(state["end_number"], 4)
        self.assertEqual(state["distance_label"], "15 yards")

    async def test_goto_command_with_bad_target_is_ignored_not_fatal(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        before = self.display.last_state()
        await self.server.handle_command(json.dumps({"action": "goto", "unit": 1, "end": 999}))
        after = self.display.last_state()
        self.assertEqual(before, after)  # unchanged, no crash


class TestMatchServerLaneTracking(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Efface tout instantané laissé par un test précédent -- voir
        # setUpModule/tearDownModule plus haut, qui isole déjà le chemin
        # lui-même, mais pas son contenu entre deux tests de ce fichier.
        config_store.clear_match_snapshot()
        self.server = MatchServer()
        self.control = FakeWebSocket()
        self.lane1 = FakeWebSocket()
        self.lane2 = FakeWebSocket()
        await self.server.register(self.control)
        await self.server.register(self.lane1)
        await self.server.register(self.lane2)

    async def test_no_lanes_connected_by_default(self) -> None:
        self.assertEqual(self.control.last_connected_lanes(), [])

    async def test_registering_a_display_adds_it_to_connected_lanes(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "3"}), self.lane1
        )
        self.assertEqual(self.control.last_connected_lanes(), ["3"])

    async def test_multiple_lanes_sorted_numerically(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "10"}), self.lane1
        )
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "2"}), self.lane2
        )
        self.assertEqual(self.control.last_connected_lanes(), ["2", "10"])

    async def test_apercu_preview_lane_is_excluded_from_the_list(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "apercu"}), self.lane1
        )
        self.assertEqual(self.control.last_connected_lanes(), [])

    async def test_unregistering_removes_the_lane(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "5"}), self.lane1
        )
        await self.server.unregister(self.lane1)
        await self.server.handle_command(json.dumps({"action": "message", "value": None}))
        self.assertEqual(self.control.last_connected_lanes(), [])

    async def test_targeted_message_only_reaches_its_lane(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "1"}), self.lane1
        )
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "2"}), self.lane2
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "message",
                    "lane": "1",
                    "value": "Message pour la lane 1 seulement",
                }
            )
        )
        self.assertEqual(self.lane1.last_message(), "Message pour la lane 1 seulement")
        self.assertIsNone(self.lane2.last_message())

    async def test_targeted_message_does_not_override_global_for_other_lanes(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "1"}), self.lane1
        )
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "2"}), self.lane2
        )
        await self.server.handle_command(
            json.dumps({"action": "message", "value": "Message global"})
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "message",
                    "lane": "1",
                    "value": "Message pour la lane 1",
                }
            )
        )
        self.assertEqual(self.lane1.last_message(), "Message pour la lane 1")
        self.assertEqual(self.lane2.last_message(), "Message global")

    async def test_clearing_a_targeted_message_falls_back_to_global(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "1"}), self.lane1
        )
        await self.server.handle_command(
            json.dumps({"action": "message", "value": "Message global"})
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "message",
                    "lane": "1",
                    "value": "Ciblé",
                }
            )
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "message",
                    "lane": "1",
                    "value": None,
                }
            )
        )
        self.assertEqual(self.lane1.last_message(), "Message global")

    async def test_global_message_after_targeted_overrides_it(self) -> None:
        """Régression : un message ciblé envoyé plus tôt ne doit pas rester
        collé sur sa lane une fois qu'un nouveau message global est envoyé."""
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "1"}), self.lane1
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "message",
                    "lane": "1",
                    "value": "Message ciblé lane 1",
                }
            )
        )
        self.assertEqual(self.lane1.last_message(), "Message ciblé lane 1")

        await self.server.handle_command(
            json.dumps({"action": "message", "value": "Nouveau message global"})
        )
        self.assertEqual(self.lane1.last_message(), "Nouveau message global")

    async def test_registration_without_websocket_argument_is_ignored_not_fatal(self) -> None:
        # handle_command called the "old" way (no websocket) must not crash --
        # e.g. any test or caller that forgot to pass it.
        await self.server.handle_command(json.dumps({"action": "register_display", "lane": "9"}))
        self.assertEqual(self.control.last_connected_lanes(), [])


class TestMatchServerConfigCommands(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Efface tout instantané laissé par un test précédent -- voir
        # setUpModule/tearDownModule plus haut, qui isole déjà le chemin
        # lui-même, mais pas son contenu entre deux tests de ce fichier.
        config_store.clear_match_snapshot()
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_indoor = config_store.INDOOR_TOML
        self._original_flint = config_store.FLINT_TOML
        self._original_app = config_store.APP_TOML
        config_store.INDOOR_TOML = Path(self._tmpdir.name) / "indoor.toml"
        config_store.FLINT_TOML = Path(self._tmpdir.name) / "flint.toml"
        config_store.APP_TOML = Path(self._tmpdir.name) / "app.toml"

        self.server = MatchServer()
        self.control = FakeWebSocket()
        await self.server.register(self.control)

    async def asyncTearDown(self) -> None:
        config_store.INDOOR_TOML = self._original_indoor
        config_store.FLINT_TOML = self._original_flint
        config_store.APP_TOML = self._original_app
        self._tmpdir.cleanup()

    async def test_get_config_returns_defaults_when_no_file_exists(self) -> None:
        await self.server.handle_command(json.dumps({"action": "get_config"}), self.control)
        payload = json.loads(self.control.sent[-1])
        self.assertEqual(payload["type"], "config")
        self.assertEqual(payload["indoor"]["shoot_time"], 240.0)
        self.assertEqual(payload["flint"]["units"], 2)

    async def test_save_config_indoor_persists_and_confirms(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 200.0},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertEqual(reply["type"], "config_saved")
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["values"]["shoot_time"], 200.0)

        # une nouvelle lecture doit refléter la valeur sauvegardée
        await self.server.handle_command(json.dumps({"action": "get_config"}), self.control)
        payload = json.loads(self.control.sent[-1])
        self.assertEqual(payload["indoor"]["shoot_time"], 200.0)

    async def test_save_config_invalid_values_reports_error_without_crashing(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 10.0, "orange_warning_time": 999.0},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertEqual(reply["type"], "config_saved")
        self.assertFalse(reply["ok"])
        self.assertIn("error", reply)

    async def test_starting_a_match_uses_the_saved_config(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 77.0, "orange_warning_time": 10.0},
                }
            ),
            self.control,
        )
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "next"}))  # RED -> GREEN
        state = self.control.last_state()
        self.assertEqual(state["time_left"], 77.0)

    async def test_starting_a_match_uses_the_saved_countdown_tick_seconds(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "app",
                    "values": {"countdown_tick_seconds": 3},
                }
            ),
            self.control,
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 120.0, "orange_warning_time": 0.0},
                }
            )
        )
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        self.server.engine.tick(10)  # RED(10) -> GREEN(120)
        self.server.engine.pop_pending_events()

        self.server.engine.tick(114)  # 120 - 114 = 6s left, pas encore dans les 3 dernières
        self.assertEqual(self.server.engine.pop_pending_events(), [])

        self.server.engine.tick(3)  # 6 - 3 = 3s left, franchit le seuil (configuré à 3, pas 5)
        self.assertIn("countdown_tick", self.server.engine.pop_pending_events())

    async def test_broadcast_includes_orange_threshold_from_current_step(self) -> None:
        """Nécessaire pour que l'écran d'affichage puisse reproduire
        localement le passage à l'orange pendant une coupure réseau (voir
        docs/architecture.md, section fonctionnement dégradé)."""
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 240.0, "orange_warning_time": 30.0},
                }
            )
        )
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "next"}))  # RED -> GREEN
        state = self.control.last_state()
        self.assertEqual(state["orange_threshold"], 30.0)

    async def test_broadcast_includes_countdown_tick_seconds(self) -> None:
        """Nécessaire pour que l'écran d'affichage puisse reproduire
        localement les bips des dernières secondes pendant une coupure
        réseau (voir docs/architecture.md)."""
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "app",
                    "values": {"countdown_tick_seconds": 7},
                }
            ),
            self.control,
        )
        self.assertEqual(json.loads(self.control.sent[-1])["countdown_tick_seconds"], 7)

    async def test_bare_start_uses_the_saved_turn_mode_without_override(self) -> None:
        """Le bouton Démarrer simplifié n'envoie plus turn_mode/alternate --
        le match doit utiliser tel quel ce qui est enregistré dans la config,
        pas retomber sur un défaut codé en dur côté serveur."""
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"turn_mode": "cd_only", "alternate_relay_order_each_series": False},
                }
            ),
            self.control,
        )
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        state = self.control.last_state()
        self.assertEqual(state["current_turn"], "C-D")

    async def test_unknown_config_mode_reports_error(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "bogus",
                    "values": {},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertFalse(reply["ok"])

    async def test_cannot_save_indoor_config_while_indoor_match_is_active(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 111.0},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"], "match_in_progress")

    async def test_cannot_save_indoor_config_while_indoor_match_is_paused(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "pause"}))
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 111.0},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertFalse(reply["ok"])

    async def test_cannot_save_indoor_config_during_emergency(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "emergency"}))
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 111.0},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertFalse(reply["ok"])

    async def test_can_save_flint_config_while_indoor_match_is_active(self) -> None:
        """Un match Indoor en cours ne doit pas bloquer la config Flint."""
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "flint",
                    "values": {"units": 3},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertTrue(reply["ok"])

    async def test_can_save_indoor_config_after_the_match_is_stopped(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(json.dumps({"action": "stop"}))
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 111.0},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertTrue(reply["ok"])

    async def test_can_save_indoor_config_when_no_match_has_ever_started(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 111.0},
                }
            ),
            self.control,
        )
        reply = json.loads(self.control.sent[-1])
        self.assertTrue(reply["ok"])

    async def test_default_sound_pack_is_classic(self) -> None:
        self.assertEqual(self.control.last_sound_pack(), "classic")

    async def test_get_config_includes_app_section(self) -> None:
        await self.server.handle_command(json.dumps({"action": "get_config"}), self.control)
        payload = json.loads(self.control.sent[-1])
        self.assertEqual(payload["app"]["sound_pack"], "classic")

    async def test_saving_sound_pack_broadcasts_immediately_to_all_clients(self) -> None:
        display = FakeWebSocket()
        await self.server.register(display)

        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "app",
                    "values": {"sound_pack": "mon_club"},
                }
            ),
            self.control,
        )

        reply = self.control.last_config_saved_reply()
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["values"]["sound_pack"], "mon_club")
        # un écran déjà connecté doit recevoir le nouveau pack tout de suite,
        # contrairement à la config Indoor/Flint qui n'agit qu'au prochain match
        self.assertEqual(display.last_sound_pack(), "mon_club")

    async def test_sound_pack_can_be_changed_while_a_match_is_in_progress(self) -> None:
        """Contrairement à la config Indoor/Flint, le pack de sons n'est
        pas bloqué par un match en cours -- il n'affecte pas les règles."""
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "app",
                    "values": {"sound_pack": "mon_club"},
                }
            ),
            self.control,
        )
        reply = self.control.last_config_saved_reply()
        self.assertTrue(reply["ok"])


class TestMatchServerAuth(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Efface tout instantané laissé par un test précédent -- voir
        # setUpModule/tearDownModule plus haut, qui isole déjà le chemin
        # lui-même, mais pas son contenu entre deux tests de ce fichier.
        config_store.clear_match_snapshot()
        self._tmpdir = tempfile.TemporaryDirectory()
        self._originals = {
            "INDOOR_TOML": config_store.INDOOR_TOML,
            "FLINT_TOML": config_store.FLINT_TOML,
            "APP_TOML": config_store.APP_TOML,
            "AUTH_TOML": config_store.AUTH_TOML,
        }
        config_store.INDOOR_TOML = Path(self._tmpdir.name) / "indoor.toml"
        config_store.FLINT_TOML = Path(self._tmpdir.name) / "flint.toml"
        config_store.APP_TOML = Path(self._tmpdir.name) / "app.toml"
        config_store.AUTH_TOML = Path(self._tmpdir.name) / "auth.toml"

        self.server = MatchServer()
        self.control = FakeWebSocket()
        await self.server.register(self.control)

    async def asyncTearDown(self) -> None:
        config_store.INDOOR_TOML = self._originals["INDOOR_TOML"]
        config_store.FLINT_TOML = self._originals["FLINT_TOML"]
        config_store.APP_TOML = self._originals["APP_TOML"]
        config_store.AUTH_TOML = self._originals["AUTH_TOML"]
        self._tmpdir.cleanup()

    def _last(self):
        return json.loads(self.control.sent[-1])

    async def test_no_password_by_default_everything_works(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        self.assertIsNotNone(self.control.last_state())

    async def test_auth_required_flag_false_by_default(self) -> None:
        self.assertFalse(self._last()["auth_required"])

    async def test_setting_the_first_password_needs_no_prior_auth(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "save_config", "mode": "auth", "values": {"password": "secret"}}),
            self.control,
        )
        reply = self.control.last_config_saved_reply()
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["values"], {"password_set": True})  # jamais le mot de passe en clair

    async def test_protected_action_blocked_once_password_is_set(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(json.dumps({"action": "start_indoor"}), self.control)
        self.assertEqual(self._last()["type"], "auth_required")

    async def test_auth_required_flag_becomes_true_once_password_is_set(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.broadcast_state()
        self.assertTrue(self._last()["auth_required"])

    async def test_wrong_password_is_rejected(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(
            json.dumps({"action": "authenticate", "password": "wrong"}), self.control
        )
        reply = self._last()
        self.assertEqual(reply["type"], "auth_result")
        self.assertFalse(reply["ok"])

    async def test_correct_password_authenticates_and_unblocks_actions(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(
            json.dumps({"action": "authenticate", "password": "secret"}), self.control
        )
        self.assertTrue(self._last()["ok"])

        await self.server.handle_command(json.dumps({"action": "start_indoor"}), self.control)
        self.assertIsNotNone(self.control.last_state())  # a bien démarré, pas rejeté

    async def test_get_config_reports_password_set_without_leaking_it(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(json.dumps({"action": "get_config"}), self.control)
        payload = self._last()
        self.assertEqual(payload["auth"], {"password_set": True})
        self.assertNotIn("secret", json.dumps(payload))  # le mot de passe ne transite jamais

    async def test_changing_password_requires_current_authentication(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        # nouvelle connexion, pas encore authentifiée
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "autre"},
                }
            ),
            self.control,
        )
        reply = self.control.last_config_saved_reply()
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"], "auth_required")

    async def test_indoor_and_flint_config_also_blocked_without_auth(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "indoor",
                    "values": {"shoot_time": 111.0},
                }
            ),
            self.control,
        )
        reply = self.control.last_config_saved_reply()
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"], "auth_required")

    async def test_get_config_and_register_display_never_need_auth(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(json.dumps({"action": "get_config"}), self.control)
        self.assertEqual(self._last()["type"], "config")

        display = FakeWebSocket()
        await self.server.register(display)
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "1"}), display
        )
        self.assertIn("1", json.loads(self.control.sent[-1])["connected_lanes"])

    async def test_unregistering_clears_authentication(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(
            json.dumps({"action": "authenticate", "password": "secret"}), self.control
        )
        self.assertTrue(self._last()["ok"])

        await self.server.unregister(self.control)
        await self.server.register(self.control)  # reconnexion (nouvelle "session")
        await self.server.handle_command(json.dumps({"action": "start_indoor"}), self.control)
        self.assertEqual(self._last()["type"], "auth_required")

    async def test_empty_password_disables_protection_again(self) -> None:
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": "secret"},
                }
            )
        )
        await self.server.handle_command(
            json.dumps({"action": "authenticate", "password": "secret"}), self.control
        )
        await self.server.handle_command(
            json.dumps(
                {
                    "action": "save_config",
                    "mode": "auth",
                    "values": {"password": ""},
                }
            ),
            self.control,
        )
        reply = self.control.last_config_saved_reply()
        self.assertTrue(reply["ok"])

        # une connexion toute neuve, jamais authentifiée, doit maintenant passer
        fresh = FakeWebSocket()
        await self.server.register(fresh)
        await self.server.handle_command(json.dumps({"action": "start_indoor"}), fresh)
        self.assertIsNotNone(fresh.last_state())


class TestMatchServerCrashRecovery(unittest.IsolatedAsyncioTestCase):
    """Couvre la récupération après un plantage/redémarrage du serveur --
    voir MatchServer._save_snapshot/_try_restore_from_snapshot et
    fletchtime.engine.engine.MatchEngine.snapshot/restore. Le chemin
    MATCH_STATE_JSON lui-même est isolé pour tout le module par
    setUpModule/tearDownModule plus haut ; ici, on efface juste son
    contenu entre deux tests de cette classe précise.
    """

    async def asyncSetUp(self) -> None:
        config_store.clear_match_snapshot()

    async def asyncTearDown(self) -> None:
        config_store.clear_match_snapshot()

    async def test_a_fresh_server_restores_a_match_in_progress(self) -> None:
        server1 = MatchServer()
        await server1.handle_command(json.dumps({"action": "start_indoor"}))
        await server1.handle_command(json.dumps({"action": "next"}))  # RED -> GREEN
        server1.engine.tick(15)
        server1._save_snapshot()  # simule la sauvegarde périodique du tick_loop
        state_before = server1.engine.current_state

        # Simule un plantage + redémarrage : un tout nouveau MatchServer,
        # sans rien de partagé avec server1 sinon le fichier sur disque.
        server2 = MatchServer()
        self.assertIsNotNone(server2.engine)
        self.assertEqual(server2.engine.current_state, state_before)
        self.assertEqual(server2._current_mode_kind, "indoor")

    async def test_no_snapshot_means_fresh_server_has_no_match(self) -> None:
        server = MatchServer()
        self.assertIsNone(server.engine)

    async def test_stop_clears_the_snapshot(self) -> None:
        server1 = MatchServer()
        await server1.handle_command(json.dumps({"action": "start_indoor"}))
        await server1.handle_command(json.dumps({"action": "stop"}))

        server2 = MatchServer()
        self.assertIsNone(server2.engine)

    async def test_restart_command_persists_the_reset_state(self) -> None:
        server1 = MatchServer()
        await server1.handle_command(json.dumps({"action": "start_indoor"}))
        await server1.handle_command(json.dumps({"action": "next"}))
        await server1.handle_command(json.dumps({"action": "restart"}))

        server2 = MatchServer()
        self.assertIsNotNone(server2.engine)
        self.assertEqual(server2.engine.current_state.phase.value, "red")

    async def test_corrupted_snapshot_file_does_not_prevent_server_startup(self) -> None:
        config_store.MATCH_STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
        config_store.MATCH_STATE_JSON.write_text("not valid json {{{", encoding="utf-8")
        server = MatchServer()  # ne doit pas lever
        self.assertIsNone(server.engine)


class TestMatchServerLogging(unittest.IsolatedAsyncioTestCase):
    """Couvre le journal applicatif (voir fletchtime.logging_setup) --
    commandes reçues, (dé)connexions, et surtout l'absence de fuite du
    mot de passe dans les journaux."""

    async def asyncSetUp(self) -> None:
        config_store.clear_match_snapshot()
        self.server = MatchServer()
        self.control = FakeWebSocket()

    async def asyncTearDown(self) -> None:
        config_store.clear_match_snapshot()

    async def test_received_command_is_logged(self) -> None:
        with self.assertLogs("fletchtime.server", level="INFO") as ctx:
            await self.server.handle_command(json.dumps({"action": "start_indoor"}), self.control)
        self.assertTrue(any("start_indoor" in line for line in ctx.output))

    async def test_connect_and_disconnect_are_logged(self) -> None:
        with self.assertLogs("fletchtime.server", level="INFO") as ctx:
            await self.server.register(self.control)
            await self.server.unregister(self.control)
        joined = "\n".join(ctx.output)
        self.assertIn("établie", joined)
        self.assertIn("perdue", joined)

    async def test_invalid_json_message_is_logged_as_warning(self) -> None:
        with self.assertLogs("fletchtime.server", level="WARNING") as ctx:
            await self.server.handle_command("pas du json {{{", self.control)
        self.assertTrue(any("invalide" in line for line in ctx.output))

    async def test_password_never_appears_in_logs(self) -> None:
        """Test de sécurité : l'action authenticate transporte le mot de
        passe en clair -- il ne doit jamais se retrouver dans un message
        de journal, où il traînerait en clair dans un fichier persistant."""
        secret = "SUPER_SECRET_PASSWORD_xyz789"
        with self.assertLogs("fletchtime.server", level="INFO") as ctx:
            await self.server.handle_command(
                json.dumps({"action": "authenticate", "password": secret}), self.control
            )
        joined = "\n".join(ctx.output)
        self.assertNotIn(secret, joined)


if __name__ == "__main__":
    unittest.main()

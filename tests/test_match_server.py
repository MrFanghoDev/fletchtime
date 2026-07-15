import json
import unittest

from fletchtime_server.match_server import MatchServer


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


class TestMatchServer(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.server = MatchServer()
        self.control = FakeWebSocket()
        self.display = FakeWebSocket()
        await self.server.register(self.control)
        await self.server.register(self.display)

    async def test_no_match_at_startup(self) -> None:
        self.assertIsNone(self.control.last_state())

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
        await self.server.handle_command(json.dumps({
            "action": "start_flint", "turn_mode": "ab_then_cd", "alternate": False,
        }))
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
        await self.server.handle_command(
            json.dumps({"action": "set_language", "value": "en"})
        )
        self.assertEqual(self.display.last_language(), "en")

    async def test_language_persists_across_match_start_and_stop(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "set_language", "value": "en"})
        )
        await self.server.handle_command(json.dumps({"action": "start_flint"}))
        self.assertEqual(self.display.last_language(), "en")
        await self.server.handle_command(json.dumps({"action": "stop"}))
        self.assertEqual(self.display.last_language(), "en")

    async def test_invalid_language_is_ignored_not_fatal(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "set_language", "value": "de"})
        )
        self.assertEqual(self.display.last_language(), "fr")  # unchanged

    async def test_default_event_title_is_none(self) -> None:
        self.assertIsNone(self.display.last_event_title())

    async def test_event_title_can_be_set(self) -> None:
        await self.server.handle_command(json.dumps({
            "action": "set_event_title", "value": "Concours FFTL Indoor -- Février 2026",
        }))
        self.assertEqual(
            self.display.last_event_title(), "Concours FFTL Indoor -- Février 2026"
        )

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
        await self.server.handle_command(
            json.dumps({"action": "set_event_title", "value": None})
        )
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
        await self.server.handle_command(json.dumps({
            "action": "start_indoor", "turn_mode": "ab_then_cd", "alternate": False,
        }))
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
        await self.server.handle_command(
            json.dumps({"action": "goto", "unit": 1, "end": 4})
        )
        state = self.display.last_state()
        self.assertEqual(state["end_number"], 4)
        self.assertEqual(state["distance_label"], "15 yards")

    async def test_goto_command_with_bad_target_is_ignored_not_fatal(self) -> None:
        await self.server.handle_command(json.dumps({"action": "start_indoor"}))
        before = self.display.last_state()
        await self.server.handle_command(
            json.dumps({"action": "goto", "unit": 1, "end": 999})
        )
        after = self.display.last_state()
        self.assertEqual(before, after)  # unchanged, no crash


class TestMatchServerLaneTracking(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
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
        await self.server.handle_command(json.dumps({
            "action": "message", "lane": "1", "value": "Message pour la lane 1 seulement",
        }))
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
        await self.server.handle_command(json.dumps({
            "action": "message", "lane": "1", "value": "Message pour la lane 1",
        }))
        self.assertEqual(self.lane1.last_message(), "Message pour la lane 1")
        self.assertEqual(self.lane2.last_message(), "Message global")

    async def test_clearing_a_targeted_message_falls_back_to_global(self) -> None:
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "1"}), self.lane1
        )
        await self.server.handle_command(
            json.dumps({"action": "message", "value": "Message global"})
        )
        await self.server.handle_command(json.dumps({
            "action": "message", "lane": "1", "value": "Ciblé",
        }))
        await self.server.handle_command(json.dumps({
            "action": "message", "lane": "1", "value": None,
        }))
        self.assertEqual(self.lane1.last_message(), "Message global")

    async def test_registration_without_websocket_argument_is_ignored_not_fatal(self) -> None:
        # handle_command called the "old" way (no websocket) must not crash --
        # e.g. any test or caller that forgot to pass it.
        await self.server.handle_command(
            json.dumps({"action": "register_display", "lane": "9"})
        )
        self.assertEqual(self.control.last_connected_lanes(), [])


if __name__ == "__main__":
    unittest.main()

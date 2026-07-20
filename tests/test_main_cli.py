"""Tests for the CLI argument parsing added to fletchtime.__main__ --
-h/--help, -V/--version, -v/--verbose, -d/--debug, --http-port/--ws-port.
"""

from __future__ import annotations

import io
import logging
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from fletchtime.__main__ import (
    _build_arg_parser,
    _resolve_console_log_level,
    _resolve_ports,
)
from fletchtime.server import config_store


class TestArgParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = _build_arg_parser()

    def test_defaults(self) -> None:
        args = self.parser.parse_args([])
        self.assertFalse(args.headless)
        self.assertFalse(args.verbose)
        self.assertFalse(args.debug)
        self.assertIsNone(args.http_port)
        self.assertIsNone(args.ws_port)

    def test_headless_flag(self) -> None:
        args = self.parser.parse_args(["--headless"])
        self.assertTrue(args.headless)

    def test_no_gui_is_an_alias_for_headless(self) -> None:
        args = self.parser.parse_args(["--no-gui"])
        self.assertTrue(args.headless)

    def test_verbose_flag(self) -> None:
        args = self.parser.parse_args(["-v"])
        self.assertTrue(args.verbose)
        args = self.parser.parse_args(["--verbose"])
        self.assertTrue(args.verbose)

    def test_debug_flag(self) -> None:
        args = self.parser.parse_args(["-d"])
        self.assertTrue(args.debug)
        args = self.parser.parse_args(["--debug"])
        self.assertTrue(args.debug)

    def test_port_options(self) -> None:
        args = self.parser.parse_args(["--http-port", "9000", "--ws-port", "9765"])
        self.assertEqual(args.http_port, 9000)
        self.assertEqual(args.ws_port, 9765)

    def test_version_prints_and_exits(self) -> None:
        # argparse's action="version" writes to stdout and raises SystemExit(0)
        with self.assertRaises(SystemExit) as ctx:
            self.parser.parse_args(["-V"])
        self.assertEqual(ctx.exception.code, 0)

    def test_help_prints_and_exits(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self.parser.parse_args(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_unknown_option_is_a_usage_error(self) -> None:
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                self.parser.parse_args(["--not-a-real-option"])
        self.assertEqual(ctx.exception.code, 2)


class TestResolveConsoleLogLevel(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = _build_arg_parser()

    def test_default_is_warning(self) -> None:
        args = self.parser.parse_args([])
        self.assertEqual(_resolve_console_log_level(args), logging.WARNING)

    def test_verbose_is_info(self) -> None:
        args = self.parser.parse_args(["-v"])
        self.assertEqual(_resolve_console_log_level(args), logging.INFO)

    def test_debug_is_debug(self) -> None:
        args = self.parser.parse_args(["-d"])
        self.assertEqual(_resolve_console_log_level(args), logging.DEBUG)

    def test_debug_wins_over_verbose_if_both_given(self) -> None:
        args = self.parser.parse_args(["-d", "-v"])
        self.assertEqual(_resolve_console_log_level(args), logging.DEBUG)


class TestResolvePorts(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = _build_arg_parser()
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_gui_toml = config_store.GUI_TOML
        config_store.GUI_TOML = Path(self._tmpdir.name) / "gui.toml"

    def tearDown(self) -> None:
        config_store.GUI_TOML = self._original_gui_toml
        self._tmpdir.cleanup()

    def test_defaults_come_from_config_when_no_cli_override(self) -> None:
        config_store.save_gui_config({"http_port": 8100, "ws_port": 8200})
        args = self.parser.parse_args([])
        http_port, ws_port = _resolve_ports(args, self.parser)
        self.assertEqual((http_port, ws_port), (8100, 8200))

    def test_cli_overrides_take_priority(self) -> None:
        config_store.save_gui_config({"http_port": 8100, "ws_port": 8200})
        args = self.parser.parse_args(["--http-port", "9100", "--ws-port", "9200"])
        http_port, ws_port = _resolve_ports(args, self.parser)
        self.assertEqual((http_port, ws_port), (9100, 9200))

    def test_cli_override_never_persists_to_config(self) -> None:
        args = self.parser.parse_args(["--http-port", "9100", "--ws-port", "9200"])
        _resolve_ports(args, self.parser)
        self.assertEqual(config_store.load_gui_config()["http_port"], 8000)  # défaut, inchangé

    def test_partial_override_still_validates_the_combined_pair(self) -> None:
        # Un seul port en ligne de commande, l'autre venant de la config --
        # les deux doivent quand même être validés ensemble.
        config_store.save_gui_config({"http_port": 8100, "ws_port": 9100})
        args = self.parser.parse_args(["--http-port", "9100"])  # entre en conflit avec ws_port
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                _resolve_ports(args, self.parser)
        self.assertEqual(ctx.exception.code, 2)

    def test_identical_ports_is_a_usage_error(self) -> None:
        args = self.parser.parse_args(["--http-port", "9000", "--ws-port", "9000"])
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                _resolve_ports(args, self.parser)
        self.assertEqual(ctx.exception.code, 2)

    def test_out_of_range_port_is_a_usage_error(self) -> None:
        args = self.parser.parse_args(["--http-port", "99999"])
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                _resolve_ports(args, self.parser)
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

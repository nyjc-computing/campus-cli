"""Unit tests for output formatting (#69: raw machine-readable --json)."""

import io
import json

from rich.console import Console

from campus_cli.utils import output


def _capturing_terminal_console(width=40) -> Console:
    """A Rich console that reports itself as a TTY and captures its output."""
    return Console(file=io.StringIO(), force_terminal=True, width=width)


class TestPrintJsonRawByDefault:
    """print_json must never mutate string values on the machine path (#69)."""

    def test_long_values_round_trip_byte_exact(self, capsys):
        """A value longer than the console width comes back unmodified."""
        long_value = "a" * 110
        output.print_json({"vault": "v", "key": "k", "value": long_value})

        payload = json.loads(capsys.readouterr().out)
        assert payload["value"] == long_value
        assert "\n" not in payload["value"]

    def test_raw_output_is_spec_valid_json(self, capsys):
        output.print_json({"values": ["x" * 200, {"nested": "y" * 90}]})
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["values"][0] == "x" * 200
        assert parsed["values"][1]["nested"] == "y" * 90

    def test_pretty_false_forces_raw_even_on_a_tty(self, capsys, monkeypatch):
        monkeypatch.setattr(output, "console", _capturing_terminal_console())

        output.print_json({"value": "z" * 200}, pretty=False)

        payload = json.loads(capsys.readouterr().out)
        assert payload["value"] == "z" * 200

    def test_agent_mode_forces_raw_even_on_a_tty(self, capsys, monkeypatch):
        """CAMPUS_CLI_AGENT opts out of display rendering (#69)."""
        terminal = _capturing_terminal_console()
        monkeypatch.setattr(output, "console", terminal)
        monkeypatch.setenv("CAMPUS_CLI_AGENT", "1")

        output.print_json({"value": "w" * 200})

        assert terminal.file.getvalue() == ""
        payload = json.loads(capsys.readouterr().out)
        assert payload["value"] == "w" * 200

    def test_agent_mode_ignores_falsy_values(self, capsys, monkeypatch):
        monkeypatch.setattr(output, "console", _capturing_terminal_console())
        monkeypatch.setenv("CAMPUS_CLI_AGENT", "0")

        output.print_json({"tty": True})
        assert capsys.readouterr().out == ""


class TestPrintJsonPrettyOnTty:
    """The Rich renderable is display-only, for interactive terminals."""

    def test_tty_gets_the_highlighted_renderable(self, capsys, monkeypatch):
        terminal = _capturing_terminal_console()
        monkeypatch.setattr(output, "console", terminal)

        output.print_json({"value": "v" * 200})

        # Pretty output goes through the Rich console, not raw stdout.
        assert terminal.file.getvalue() != ""
        assert capsys.readouterr().out == ""

    def test_pretty_true_forces_the_renderable(self, capsys, monkeypatch):
        terminal = _capturing_terminal_console()
        monkeypatch.setattr(output, "console", terminal)

        output.print_json({"value": "v"}, pretty=True)

        assert terminal.file.getvalue() != ""
        assert capsys.readouterr().out == ""

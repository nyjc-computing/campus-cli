"""Unit tests for the clipboard helper's mechanism fallback (#43)."""

import base64
import sys
from unittest import mock

import pyperclip

from campus_cli.utils.clipboard import copy_to_clipboard


def test_working_native_mechanism_reports_native():
    """A functional pyperclip mechanism reports a definitive copy."""
    with mock.patch.object(pyperclip, "copy") as mock_copy:
        assert copy_to_clipboard("2S2L-3V92") == "native"

    mock_copy.assert_called_once_with("2S2L-3V92")


def test_native_failure_falls_through_to_osc52(capsys):
    """A host without a native mechanism tries the OSC 52 sequence."""
    with (
        mock.patch.object(
            pyperclip, "copy",
            side_effect=pyperclip.PyperclipException("no xclip"),
        ),
        mock.patch.object(sys.stdout, "isatty", return_value=True),
    ):
        assert copy_to_clipboard("2S2L-3V92") == "osc52"

    payload = base64.b64encode(b"2S2L-3V92").decode("ascii")
    assert f"\x1b]52;c;{payload}\x07" in capsys.readouterr().out


def test_missing_pyperclip_on_tty_falls_through_to_osc52(capsys):
    """A missing pyperclip install behaves like a missing mechanism."""
    with (
        mock.patch.dict(sys.modules, {"pyperclip": None}),
        mock.patch.object(sys.stdout, "isatty", return_value=True),
    ):
        assert copy_to_clipboard("2S2L-3V92") == "osc52"

    payload = base64.b64encode(b"2S2L-3V92").decode("ascii")
    assert f"\x1b]52;c;{payload}\x07" in capsys.readouterr().out


def test_piped_output_never_receives_escape_bytes(capsys):
    """Non-TTY stdout suppresses OSC 52: no mechanism, nothing emitted."""
    with (
        mock.patch.dict(sys.modules, {"pyperclip": None}),
        mock.patch.object(sys.stdout, "isatty", return_value=False),
    ):
        assert copy_to_clipboard("2S2L-3V92") == "failed"

    assert "\x1b" not in capsys.readouterr().out


def test_osc52_wraps_escape_sequence_inside_tmux(capsys):
    """tmux sessions get the DCS passthrough wrapper with doubled ESCs."""
    with (
        mock.patch.dict(sys.modules, {"pyperclip": None}),
        mock.patch.dict("os.environ", {"TMUX": "/tmp/tmux-0/default,1,0"}),
        mock.patch.object(sys.stdout, "isatty", return_value=True),
    ):
        assert copy_to_clipboard("A") == "osc52"

    inner = f"\x1b]52;c;{base64.b64encode(b'A').decode('ascii')}\x07"
    wrapped = f"\x1bPtmux;{inner.replace(chr(27), chr(27) * 2)}\x1b\\"
    assert capsys.readouterr().out == wrapped

"""Clipboard helpers for the device-flow login UX (#43).

Two mechanisms, tried in order by copy_to_clipboard:

1. pyperclip — native OS tooling (pbcopy, clip.exe/ctypes, xclip/xsel/
   wl-copy; WSL-aware). Definitive success/failure, but only works where
   the CLI process has a desktop session: over plain SSH the remote host
   is usually headless and every mechanism is missing.
2. OSC 52 — an escape sequence that asks the *local* terminal emulator
   to set its clipboard. The sequence travels back through the SSH
   channel, so this is the only mechanism needing no remote tooling.
   Terminals acknowledge nothing, though, and support varies (tmux
   needs set-clipboard or a passthrough wrapper; iTerm2 requires
   opt-in; VTE-based terminals ignore it), so callers must hedge.
"""

import base64
import os
import sys
from typing import Literal

# "native": copied via OS tooling (definitive). "osc52": the escape
# sequence was emitted to the terminal — "sent", not confirmed.
# "failed": no mechanism available; the printed code is all there is.
CopyResult = Literal["native", "osc52", "failed"]


def copy_to_clipboard(text: str) -> CopyResult:
    """Copy text to the clipboard, best-effort.

    Tries native OS tooling first, then the OSC 52 terminal escape
    sequence (which also works through plain SSH connections in
    terminals that support it). Never raises.
    """
    if _copy_native(text):
        return "native"
    if _emit_osc52(text):
        return "osc52"
    return "failed"


def _copy_native(text: str) -> bool:
    """Copy via pyperclip; False when the host has no mechanism."""
    try:
        import pyperclip
    except ImportError:
        return False
    try:
        pyperclip.copy(text)
        return True
    except pyperclip.PyperclipException:
        return False


def _emit_osc52(text: str) -> bool:
    """Ask the terminal emulator to copy text via OSC 52.

    Only meaningful on a TTY: piped output must not receive escape
    bytes. Returns True when the sequence was written; whether the
    terminal honored it is unknowable from here.
    """
    if not sys.stdout.isatty():
        return False
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    sequence = f"\x1b]52;c;{payload}\x07"
    if os.environ.get("TMUX"):
        # tmux swallows unknown escape sequences unless they arrive as a
        # DCS passthrough; each ESC inside must be doubled.
        sequence = f"\x1bPtmux;{sequence.replace(chr(27), chr(27) * 2)}\x1b\\"
    sys.stdout.write(sequence)
    sys.stdout.flush()
    return True

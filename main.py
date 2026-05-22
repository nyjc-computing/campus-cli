"""Main entry point for campus CLI.

CRITICAL: This file exists to work around a Poetry Windows shim bug.

Poetry on Windows generates broken .exe shims that hardcode 'from main import main'
instead of correctly parsing the entry point 'campus_cli.cli:app'. Without this file,
running 'campus.exe' fails with 'ModuleNotFoundError: No module named main'.

This file must be at the repository root (not inside campus_cli/) because the shim
looks for 'main' as a top-level module.

DO NOT REMOVE this file without verifying the campus.exe shim works on Windows.
"""

from campus_cli.cli import main

__all__ = ["main"]

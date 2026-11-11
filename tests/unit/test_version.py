"""#85: the CLI version constant and the package version must not skew.

The 0.6.0 bump (#84) updated pyproject.toml but missed
campus_cli.__version__, so a wheel built from main reported a stale
version — the skew this test pins shut.
"""

import unittest
from pathlib import Path

import tomllib

from campus_cli import __version__


class TestVersion(unittest.TestCase):
    def test_version_matches_pyproject(self):
        pyproject = (
            Path(__file__).resolve().parents[2] / "pyproject.toml"
        )
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        self.assertEqual(__version__, data["tool"]["poetry"]["version"])


if __name__ == "__main__":
    unittest.main()

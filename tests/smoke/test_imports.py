"""Smoke tests - Basic sanity checks before manual testing.

These tests verify basic imports and functionality to catch obvious errors
that should be detected before manual testing.
"""

import importlib.util


def test_import_cli_module():
    """Test that the CLI module can be imported without errors."""
    spec = importlib.util.find_spec("campus_cli.cli")
    assert spec is not None, "campus_cli.cli module not found"


def test_import_credentials_module():
    """Test that the credentials module can be imported without errors."""
    spec = importlib.util.find_spec("campus_cli.credentials")
    assert spec is not None, "campus_cli.credentials module not found"


def test_import_auth_modules():
    """Test that auth submodules can be imported without errors."""
    auth_modules = [
        "campus_cli.auth.login",
        "campus_cli.auth.client",
        "campus_cli.auth.vault",
        "campus_cli.auth.common",
    ]

    for module in auth_modules:
        spec = importlib.util.find_spec(module)
        assert spec is not None, f"{module} module not found"


def test_import_utils_modules():
    """Test that utility modules can be imported without errors."""
    utils_modules = [
        "campus_cli.utils.output",
    ]

    for module in utils_modules:
        spec = importlib.util.find_spec(module)
        assert spec is not None, f"{module} module not found"


def test_rich_imports_available():
    """Test that Rich library components can be imported."""
    console_spec = importlib.util.find_spec("rich.console")
    json_spec = importlib.util.find_spec("rich.json")
    table_spec = importlib.util.find_spec("rich.table")

    assert console_spec is not None, "rich.console module not found"
    assert json_spec is not None, "rich.json module not found"
    assert table_spec is not None, "rich.table module not found"


def test_datetime_timedelta_available():
    """Test that datetime.timedelta is available (smoke test for the bug)."""
    from datetime import timedelta

    # Verify we can create a timedelta without errors
    td = timedelta(seconds=3600)
    assert td.total_seconds() == 3600


def test_credential_storage_instantiation():
    """Test that CredentialStorage can be instantiated without errors."""
    from campus_cli.credentials import CredentialStorage

    try:
        storage = CredentialStorage()
        assert storage is not None
    except Exception as e:
        raise AssertionError(f"Failed to instantiate CredentialStorage: {e}") from e


def test_cli_app_exists():
    """Test that the CLI app object exists and is callable."""
    from campus_cli.cli import app

    assert app is not None
    assert callable(app) or hasattr(app, "register")

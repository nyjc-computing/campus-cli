"""Smoke tests - Basic sanity checks before manual testing.

These tests verify basic imports and functionality to catch obvious errors
that should be detected before manual testing.
"""


def test_import_cli_module():
    """Test that the CLI module can be imported without errors."""
    try:
        import campus_cli.cli
        assert True
    except ImportError as e:
        assert False, f"Failed to import campus_cli.cli: {e}"


def test_import_credentials_module():
    """Test that the credentials module can be imported without errors."""
    try:
        import campus_cli.credentials
        assert True
    except ImportError as e:
        assert False, f"Failed to import campus_cli.credentials: {e}"


def test_import_auth_modules():
    """Test that auth submodules can be imported without errors."""
    auth_modules = [
        "campus_cli.auth.login",
        "campus_cli.auth.logout",
        "campus_cli.auth.status",
        "campus_cli.auth.client",
        "campus_cli.auth.vault",
    ]

    for module in auth_modules:
        try:
            __import__(module)
            assert True
        except ImportError as e:
            assert False, f"Failed to import {module}: {e}"


def test_import_utils_modules():
    """Test that utility modules can be imported without errors."""
    utils_modules = [
        "campus_cli.utils.output",
        "campus_cli.utils.config",
    ]

    for module in utils_modules:
        try:
            __import__(module)
            assert True
        except ImportError as e:
            assert False, f"Failed to import {module}: {e}"


def test_rich_imports_available():
    """Test that Rich library components can be imported."""
    try:
        from rich.console import Console
        from rich.json import RichJson
        from rich.table import Table
        assert True
    except ImportError as e:
        assert False, f"Failed to import Rich components: {e}"


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
        assert False, f"Failed to instantiate CredentialStorage: {e}"


def test_cli_app_exists():
    """Test that the CLI app object exists and is callable."""
    from campus_cli.cli import app

    assert app is not None
    assert hasattr(app, "__call__") or hasattr(app, "register")

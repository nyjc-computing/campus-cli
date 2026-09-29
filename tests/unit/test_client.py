"""Unit tests for client output formatting."""

from datetime import datetime, timezone
from types import SimpleNamespace

from campus_cli.auth.client import _format_client


def _client(created_at):
    return SimpleNamespace(
        id="uid-client-ab12cd34",
        name="Test Client",
        description="A test client",
        created_at=created_at,
        permissions={"campus.api": 1},
    )


def test_format_client_with_datetime_created_at():
    """Locally-constructed models carry a datetime created_at."""
    dt = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
    result = _format_client(_client(dt))
    assert result["created_at"] == "2026-09-29T10:00:00+00:00"


def test_format_client_with_string_created_at():
    """from_resource models carry created_at as an ISO string verbatim."""
    result = _format_client(_client("2026-09-29T10:00:00+00:00"))
    assert result["created_at"] == "2026-09-29T10:00:00+00:00"


def test_format_client_with_none_created_at():
    """created_at may be absent/None."""
    result = _format_client(_client(None))
    assert result["created_at"] is None

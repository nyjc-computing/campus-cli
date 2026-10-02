"""Unit tests for client output formatting."""

from datetime import datetime, timezone
from types import SimpleNamespace

from campus_cli.auth.client import _format_client


def _client(created_at, **overrides):
    fields = {
        "id": "uid-client-ab12cd34",
        "name": "Test Client",
        "description": "A test client",
        "created_at": created_at,
        "permissions": {"campus.api": 1},
        "redirect_uris": [],
        "allowed_scopes": [],
        "upstream_scopes": {},
        "token_bridge": False,
        "is_public": False,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


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


def test_format_client_includes_redirect_uris_and_is_public():
    """issue #21: JSON output must carry redirect_uris and is_public."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00",
        redirect_uris=["https://example.edu/callback"],
        is_public=True,
    ))
    assert result["redirect_uris"] == ["https://example.edu/callback"]
    assert result["is_public"] is True


def test_format_client_coerces_none_redirect_uris_to_empty_list():
    """A null redirect_uris projects as [] so the field is always present."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00", redirect_uris=None
    ))
    assert result["redirect_uris"] == []
    assert result["is_public"] is False


def test_format_client_includes_scope_and_bridge_fields():
    """campus-cli#24: JSON output must carry the fail-closed admin fields."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00",
        allowed_scopes=["openid", "campus.api"],
        upstream_scopes={"google": ["https://www.googleapis.com/auth/calendar"]},
        token_bridge=True,
    ))
    assert result["allowed_scopes"] == ["openid", "campus.api"]
    assert result["upstream_scopes"] == {
        "google": ["https://www.googleapis.com/auth/calendar"]
    }
    assert result["token_bridge"] is True


def test_format_client_defaults_scope_fields_when_none():
    """Null scope/bridge fields project as empty values, always present."""
    result = _format_client(_client(
        "2026-09-29T10:00:00+00:00",
        allowed_scopes=None,
        upstream_scopes=None,
        token_bridge=None,
    ))
    assert result["allowed_scopes"] == []
    assert result["upstream_scopes"] == {}
    assert result["token_bridge"] is False

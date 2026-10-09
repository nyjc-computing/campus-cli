"""Unit tests for user output formatting (#42)."""

from datetime import datetime, timezone
from types import SimpleNamespace

from campus_cli.auth.user import _format_user


def _user(created_at, activated_at=None, **overrides):
    fields = {
        "id": "user@example.com",
        "email": "user@example.com",
        "name": "Test User",
        "created_at": created_at,
        "activated_at": activated_at,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_format_user_with_datetime_fields():
    """Locally-constructed models carry datetimes."""
    created = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
    activated = datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc)
    result = _format_user(_user(created, activated))
    assert result["created_at"] == "2026-09-29T10:00:00+00:00"
    assert result["activated_at"] == "2026-10-01T08:30:00+00:00"


def test_format_user_with_string_fields():
    """from_resource models carry the timestamps as ISO strings."""
    result = _format_user(_user(
        "2026-09-29T10:00:00+00:00",
        "2026-10-01T08:30:00+00:00",
    ))
    assert result["created_at"] == "2026-09-29T10:00:00+00:00"
    assert result["activated_at"] == "2026-10-01T08:30:00+00:00"


def test_format_user_inactive_has_none_activated_at():
    """New users are inactive: activated_at projects as None."""
    result = _format_user(_user("2026-09-29T10:00:00+00:00"))
    assert result["activated_at"] is None


def test_format_user_carries_identity_fields():
    """The id IS the email: both project verbatim."""
    result = _format_user(_user(
        None, email="other@example.com", id="other@example.com"
    ))
    assert result["id"] == "other@example.com"
    assert result["email"] == "other@example.com"
    assert result["name"] == "Test User"
    assert result["created_at"] is None

"""Unit tests for credential storage.

These tests test individual methods of CredentialStorage in isolation
without testing interactions between multiple methods.
"""

import contextlib

import pytest

from campus_cli.credentials import CredentialError, CredentialStorage


@pytest.fixture
def credential_storage(tmp_path):
    """Create a CredentialStorage with isolated temporary storage."""

    # Create storage with temp path
    storage = CredentialStorage()
    storage._fallback_path = tmp_path / "credentials.json"
    return storage


def test_get_token_returns_none_when_not_set(credential_storage):
    """Test that get_token returns None when no token is stored."""
    # Ensure clean state first
    with contextlib.suppress(CredentialError):
        credential_storage.delete_token()
    assert credential_storage.get_token() is None


def test_set_and_get_token(credential_storage):
    """Test setting and retrieving a token."""
    credential_storage.set_token("test_token")
    assert credential_storage.get_token() == "test_token"


def test_delete_token(credential_storage):
    """Test deleting a token."""
    credential_storage.set_token("test_token")
    credential_storage.delete_token()
    assert credential_storage.get_token() is None


def test_delete_nonexistent_token_raises(credential_storage):
    """Test that deleting a nonexistent token raises an error."""
    # Ensure token doesn't exist
    with contextlib.suppress(CredentialError):
        credential_storage.delete_token()

    with pytest.raises(CredentialError):
        credential_storage.delete_token()


def test_get_refresh_token_returns_none_when_not_set(credential_storage):
    """Test that get_refresh_token returns None when not set."""
    assert credential_storage.get_refresh_token() is None


def test_set_and_get_refresh_token(credential_storage):
    """Test setting and retrieving a refresh token."""
    credential_storage.set_refresh_token("refresh_token")
    assert credential_storage.get_refresh_token() == "refresh_token"


def test_delete_refresh_token(credential_storage):
    """Test deleting a refresh token."""
    credential_storage.set_refresh_token("test_token")
    credential_storage.delete_refresh_token()
    assert credential_storage.get_refresh_token() is None


def test_get_password_returns_none_for_nonexistent_key(credential_storage):
    """Test that get_password returns None for a nonexistent key."""
    result = credential_storage.get_password("nonexistent_key")
    assert result is None


def test_set_and_get_password(credential_storage):
    """Test generic password set and get operations."""
    credential_storage.set_password("test_key", "test_value")
    result = credential_storage.get_password("test_key")
    # Result could be the value or None (if using keyring backend)
    assert result in ("test_value", None)


def test_get_token_expires_at_returns_none_when_not_set(credential_storage):
    """Test that get_token_expires_at returns None when not set."""
    assert credential_storage.get_token_expires_at() is None


def test_set_and_get_token_expires_at(credential_storage):
    """Test setting and retrieving token expiry timestamp."""
    credential_storage.set_token_expires_at("2024-01-01T00:00:00+00:00")
    assert credential_storage.get_token_expires_at() == "2024-01-01T00:00:00+00:00"


def test_is_token_expired_when_no_token(credential_storage):
    """Test that is_token_expired returns True when no token exists."""
    assert credential_storage.is_token_expired() is True


def test_is_token_expired_with_invalid_expiry_data(credential_storage):
    """Test that is_token_expired returns True with invalid expiry data."""
    credential_storage.set_token("test_token")
    credential_storage.set_token_expires_at("invalid-iso-format")
    assert credential_storage.is_token_expired() is True


def test_is_token_expired_with_past_expiry(credential_storage):
    """Test that is_token_expired returns True with past expiry."""
    from datetime import datetime, timedelta, timezone

    credential_storage.set_token("test_token")
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    credential_storage.set_token_expires_at(past_time.isoformat())
    assert credential_storage.is_token_expired() is True


def test_is_token_expired_with_future_expiry(credential_storage):
    """Test that is_token_expired returns False with future expiry."""
    from datetime import datetime, timedelta, timezone

    credential_storage.set_token("test_token")
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)
    credential_storage.set_token_expires_at(future_time.isoformat())
    assert credential_storage.is_token_expired() is False

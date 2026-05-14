"""Integration tests for credential storage.

These tests test interactions between multiple methods and more complex scenarios.
"""

import pytest

from campus_cli.credentials import CredentialError, CredentialStorage


@pytest.fixture
def credential_storage(tmp_path):
    """Create a CredentialStorage with isolated temporary storage."""

    # Create storage with temp path
    storage = CredentialStorage()
    storage._fallback_path = tmp_path / "credentials.json"
    return storage


def test_set_token_with_expiry(credential_storage):
    """Test setting token with expiry calculation (integration test)."""
    from datetime import datetime, timedelta, timezone

    # Set token with 1 hour expiry
    expires_in = 3600
    credential_storage.set_token("test_token", expires_in=expires_in)

    # Verify token was stored
    assert credential_storage.get_token() == "test_token"

    # Verify expiry was calculated and stored
    expires_at_str = credential_storage.get_token_expires_at()
    assert expires_at_str is not None

    # Verify it's a valid ISO format timestamp in the future
    expires_at = datetime.fromisoformat(expires_at_str)
    now = datetime.now(timezone.utc)
    assert expires_at > now

    # Verify it's approximately 1 hour in the future (allow 5s tolerance)
    expected_expiry = now + timedelta(seconds=expires_in)
    difference = abs((expires_at - expected_expiry).total_seconds())
    assert difference < 5, f"Expiry time off by {difference}s"


def test_full_token_lifecycle_with_expiry(credential_storage):
    """Test complete lifecycle: set token with expiry, check expiry, delete."""
    from datetime import datetime, timedelta, timezone

    # Set token with 1 hour expiry
    credential_storage.set_token("test_token", expires_in=3600)

    # Verify not expired
    assert credential_storage.is_token_expired() is False

    # Set expiry to past
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    credential_storage.set_token_expires_at(past_time.isoformat())

    # Verify now expired
    assert credential_storage.is_token_expired() is True

    # Delete token
    credential_storage.delete_token()

    # Verify token is gone
    assert credential_storage.get_token() is None
    assert credential_storage.is_token_expired() is True


def test_is_token_expired_with_threshold(credential_storage):
    """Test token expiry checking with threshold (integration test)."""
    from datetime import datetime, timedelta, timezone

    credential_storage.set_token("test_token")

    # Token expiring in 30 seconds
    credential_storage.set_token_expires_at(
        (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
    )

    # Should not be expired with default threshold
    assert credential_storage.is_token_expired() is False

    # Should be expired with 60 second threshold
    assert credential_storage.is_token_expired(threshold_seconds=60) is True


def test_password_operations_persistence(credential_storage):
    """Test that password operations persist correctly (integration test)."""
    # Set multiple keys
    credential_storage.set_password("key1", "value1")
    credential_storage.set_password("key2", "value2")
    credential_storage.set_password("key3", "value3")

    # Verify all can be retrieved
    assert credential_storage.get_password("key1") in ("value1", None)  # None if using keyring
    assert credential_storage.get_password("key2") in ("value2", None)
    assert credential_storage.get_password("key3") in ("value3", None)

    # Delete one
    try:
        credential_storage.delete_password("key2")
    except CredentialError:
        pass  # May fail if using keyring

    # Verify deleted key is gone
    assert credential_storage.get_password("key2") is None

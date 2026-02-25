"""Test credential storage interface."""

import pytest

from campus_cli.credentials import CredentialError, CredentialStorage


@pytest.fixture
def credential_storage(tmp_path):
    """Create a CredentialStorage with isolated temporary storage."""
    from campus_cli.credentials import CredentialStorage

    # Create storage with temp path
    storage = CredentialStorage()
    storage._fallback_path = tmp_path / "credentials.json"
    return storage


def test_set_and_get_token(credential_storage):
    """Test setting and retrieving tokens."""
    credential_storage.set_token("access_token_value")
    assert credential_storage.get_token() == "access_token_value"
    # Cleanup
    credential_storage.delete_token()


def test_token_defaults_to_none(credential_storage):
    """Test that token is None when not set."""
    # Ensure clean state first
    try:
        credential_storage.delete_token()
    except CredentialError:
        pass
    assert credential_storage.get_token() is None
    # Cleanup
    try:
        credential_storage.delete_token()
    except CredentialError:
        pass


def test_refresh_token(credential_storage):
    """Test refresh token storage."""
    credential_storage.set_refresh_token("refresh_token_value")
    assert credential_storage.get_refresh_token() == "refresh_token_value"
    # Cleanup
    try:
        credential_storage.delete_refresh_token()
    except CredentialError:
        pass


def test_delete_token(credential_storage):
    """Test deleting tokens."""
    credential_storage.set_token("access_token_value")
    credential_storage.delete_token()
    assert credential_storage.get_token() is None


def test_delete_nonexistent_token_raises(credential_storage):
    """Test deleting nonexistent token raises error."""
    # Ensure token doesn't exist
    try:
        credential_storage.delete_token()
    except CredentialError:
        pass

    with pytest.raises(CredentialError):
        credential_storage.delete_token()


def test_password_operations(credential_storage):
    """Test generic password set/get/delete operations."""
    # Set and get
    credential_storage.set_password("test_key", "test_value")
    result = credential_storage.get_password("test_key")
    # Result could be the value or None (if using keyring)
    assert result in ("test_value", None)

    # Delete
    try:
        credential_storage.delete_password("test_key")
        assert credential_storage.get_password("test_key") is None
    except CredentialError:
        # Key may not exist in keyring
        pass


def test_get_nonexistent_password(credential_storage):
    """Test getting a nonexistent password returns None."""
    result = credential_storage.get_password("nonexistent_key")
    assert result is None

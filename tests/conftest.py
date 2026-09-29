"""Shared pytest fixtures for the campus-cli test suite."""

import contextlib

import keyring
import pytest

from campus_cli.credentials import CredentialStorage

# Test-only keyring service name. Keeps everything the suite writes separate
# from the real "campus-cli" service used by `campus auth login`, which a
# working keyring backend would otherwise hit directly.
TEST_SERVICE_NAME = "campus-cli-test"


@pytest.fixture
def credential_storage(tmp_path, monkeypatch):
    """Create a CredentialStorage with isolated temporary storage.

    Redirects both backends away from the developer's real state: the keyring
    service name points at TEST_SERVICE_NAME, and the file fallback lives in a
    pytest tmp_path. Keys written during the test are tracked and deleted from
    the keyring afterwards, so even a failing test leaves nothing behind.
    """
    monkeypatch.setattr(CredentialStorage, "SERVICE_NAME", TEST_SERVICE_NAME)

    written_keys: set[str] = set()
    original_set_password = CredentialStorage.set_password

    def tracking_set_password(self: CredentialStorage, key: str, value: str) -> None:
        written_keys.add(key)
        original_set_password(self, key, value)

    monkeypatch.setattr(CredentialStorage, "set_password", tracking_set_password)

    storage = CredentialStorage()
    storage._fallback_path = tmp_path / "credentials.json"
    yield storage

    # Best-effort cleanup of keyring entries under the test service name.
    for key in written_keys:
        with contextlib.suppress(Exception):
            keyring.delete_password(TEST_SERVICE_NAME, key)

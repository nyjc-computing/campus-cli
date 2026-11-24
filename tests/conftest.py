"""Shared pytest fixtures for the campus-cli test suite."""

import contextlib

import keyring
import pytest

from campus_cli.credentials import CredentialStorage, session_key

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
    original_set_password_at = CredentialStorage.set_password_at

    def tracking_set_password(self: CredentialStorage, key: str, value: str) -> None:
        written_keys.add(key)
        original_set_password(self, key, value)

    def tracking_set_password_at(
        self: CredentialStorage, session: str | None, key: str, value: str
    ) -> None:
        # The _at primitives take the final key path themselves, so
        # track the resolved name for cleanup (audit keys route to the
        # default slot even from a session-bound instance, #113).
        written_keys.add(session_key(session, key))
        original_set_password_at(self, session, key, value)

    monkeypatch.setattr(CredentialStorage, "set_password", tracking_set_password)
    monkeypatch.setattr(
        CredentialStorage, "set_password_at", tracking_set_password_at
    )

    storage = CredentialStorage()
    storage._fallback_path = tmp_path / "credentials.json"
    yield storage

    # Best-effort cleanup of keyring entries under the test service name.
    for key in written_keys:
        with contextlib.suppress(Exception):
            keyring.delete_password(TEST_SERVICE_NAME, key)


@pytest.fixture
def make_storage(request, tmp_path):
    """Factory for storage instances bound to specific session slots (#113).

    Activates the credential_storage fixture for its class-level
    test-service patches; every instance the factory builds shares the
    tmp fallback file.
    """
    request.getfixturevalue("credential_storage")

    def _make(session: str | None = None) -> CredentialStorage:
        storage = CredentialStorage(session=session)
        storage._fallback_path = tmp_path / "credentials.json"
        return storage

    return _make

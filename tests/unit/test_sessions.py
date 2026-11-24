"""Unit tests for named login sessions (#113).

Covers the slot-addressable credential store, the session index in the
config file, and the login --as / logout --as --all / use / status --all
surface. Everything runs against isolated tmp storage and config; no
test touches the developer's real keyring entries, config file, or the
network.
"""

import json
from unittest import mock

import pytest
from typer.testing import CliRunner

from campus_cli.auth import common
from campus_cli.cli import app
from campus_cli.config import Config
from campus_cli.credentials import (
    CredentialStorage,
    session_key,
    validate_session_name,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """A tmp config file for every module the session surface touches.

    The session commands write the active-session pointer and the
    session index; tests must never touch the developer's real file.
    """
    cfg = Config(config_path=tmp_path / "config.json")
    monkeypatch.setattr("campus_cli.auth.login.config", cfg)
    monkeypatch.setattr("campus_cli.auth.status.config", cfg)
    return cfg


@pytest.fixture(autouse=True)
def isolated_stores(tmp_path, monkeypatch):
    """Route every storage instance (any slot) away from real state.

    Patches the class, so the import-time singleton and every
    session_storage() factory product are covered, on both backends.
    """
    monkeypatch.setattr(CredentialStorage, "SERVICE_NAME", "campus-cli-test")
    monkeypatch.setattr(
        CredentialStorage,
        "_get_fallback_path",
        lambda _self: tmp_path / "credentials.json",
    )


# --- credential store slots -------------------------------------------------


def test_named_slot_keys_are_namespaced(make_storage):
    """A named slot's keys never leak into the default slot's view."""
    default = make_storage(None)
    work = make_storage("work")
    work.set_password("access_token", "tok-work")

    assert work.get_password("access_token") == "tok-work"
    assert default.get_password("access_token") is None


def test_session_key_layout():
    """Slots namespace as session/<name>/<key>; the default stays flat."""
    assert session_key(None, "access_token") == "access_token"
    assert session_key("work", "access_token") == "session/work/access_token"


def test_slot_tokens_are_independent(make_storage):
    """Each slot holds its own token set with its own expiry (#113)."""
    default = make_storage(None)
    work = make_storage("work")
    default.set_token("tok-default", expires_in=3600)
    work.set_token("tok-work", expires_in=7200)

    assert default.get_token() == "tok-default"
    assert work.get_token() == "tok-work"
    assert default.is_token_expired() is False
    assert work.is_token_expired() is False

    work.delete_token()
    assert work.get_token() is None
    assert default.get_token() == "tok-default"


def test_audit_api_key_is_global_across_slots(make_storage):
    """The campus.audit key stays a per-install credential (#113)."""
    default = make_storage(None)
    work = make_storage("work")
    work.set_audit_api_key("audit_v1_k", "https://audit.example.com")

    assert default.get_audit_api_key() == "audit_v1_k"
    assert work.get_audit_api_key() == "audit_v1_k"

    default.delete_audit_api_key()
    assert work.get_audit_api_key() is None


def test_validate_session_name():
    """Names are path-segment-safe; violations name the rule."""
    assert validate_session_name("work") == "work"
    assert validate_session_name("Agent-1.prod_x") == "Agent-1.prod_x"
    for bad in ("", "-lead", "has/slash", "has space", "x" * 65):
        with pytest.raises(ValueError):
            validate_session_name(bad)


def test_endpoint_mismatch_reads_given_slot():
    """endpoint_mismatch can check a specific slot (login --as)."""
    slot = mock.Mock()
    slot.get_token_auth_url.return_value = (
        "https://auth-other.example.com/auth/v1"
    )
    with mock.patch(
        "campus_cli.auth.common.resolve_auth_url",
        return_value="https://auth-dev.example.com/auth/v1",
    ):
        mismatch = common.endpoint_mismatch(slot)
    assert mismatch == (
        "https://auth-other.example.com/auth/v1",
        "https://auth-dev.example.com/auth/v1",
    )

    slot.get_token_auth_url.return_value = None
    assert common.endpoint_mismatch(slot) is None


# --- config: active pointer + index -----------------------------------------


def test_active_session_roundtrip(tmp_path):
    """The active-session pointer persists as null or a name."""
    cfg = Config(config_path=tmp_path / "config.json")
    assert cfg.active_session is None

    cfg.active_session = "work"
    assert cfg.active_session == "work"
    assert (
        Config(config_path=tmp_path / "config.json").active_session == "work"
    )

    cfg.active_session = None
    assert cfg.active_session is None


def test_session_index_add_remove(tmp_path):
    """The index dedupes on add and tolerates unknown removals."""
    cfg = Config(config_path=tmp_path / "config.json")
    assert cfg.get_sessions() == []

    cfg.add_session("work")
    cfg.add_session("agent")
    cfg.add_session("work")
    assert cfg.get_sessions() == ["work", "agent"]

    cfg.remove_session("work")
    assert cfg.get_sessions() == ["agent"]
    cfg.remove_session("never-existed")
    assert cfg.get_sessions() == ["agent"]


# --- login --as ---------------------------------------------------------------


def _device_data():
    return {
        "device_code": "dc",
        "user_code": "ABCD-EFGH",
        "verification_uri": "https://auth.example.com/activate",
        "verification_uri_complete": (
            "https://auth.example.com/activate?user_code=ABCD-EFGH"
        ),
        "interval": 1,
        "expires_in": 300,
    }


def _token_data():
    return {
        "access_token": "tok-123",
        "refresh_token": "refresh-123",
        "expires_in": 3600,
        "user_id": "user-alice@example.com",
    }


def _run_login(args):
    """Invoke `auth login` with the device flow mocked end to end.

    The default-slot store is a Mock; session_storage is a Mock factory
    returning one named-slot Mock, so tests can assert which slot was
    written without touching real storage.
    """
    slot_creds = mock.Mock()
    slot_creds.get_token.return_value = None
    with (
        mock.patch("campus_cli.auth.login.credentials") as default_creds,
        mock.patch(
            "campus_cli.auth.login.session_storage", return_value=slot_creds
        ) as factory,
        mock.patch(
            "campus_cli.auth.login.request_device_code", return_value=_device_data()
        ),
        mock.patch(
            "campus_cli.auth.login.poll_for_token", return_value=_token_data()
        ),
        mock.patch("campus_cli.auth.login.webbrowser.open"),
        mock.patch("campus_cli.auth.login.copy_to_clipboard"),
        mock.patch(
            "campus_cli.auth.login.create_login_session", return_value=None
        ),
    ):
        result = runner.invoke(app, ["auth", "login", *args])
    return result, default_creds, slot_creds, factory


def test_login_as_stores_named_slot_and_activates(isolated_config):
    """--as writes the named slot, indexes it, and activates it."""
    result, default_creds, slot_creds, factory = _run_login(["--as", "work"])

    assert result.exit_code == 0, result.output
    factory.assert_called_once_with("work")
    slot_creds.set_token.assert_called_once()
    slot_creds.set_token_auth_url.assert_called_once()
    default_creds.set_token.assert_not_called()
    assert isolated_config.active_session == "work"
    assert isolated_config.get_sessions() == ["work"]
    assert "Active session: work" in result.output


def test_login_as_rejects_invalid_name():
    """An unsafe session name is refused before any device-flow call."""
    result, _default, _slot, factory = _run_login(["--as", "bad/slash"])

    assert result.exit_code == 1, result.output
    factory.assert_not_called()
    assert "Session names" in result.stderr


def test_login_without_as_writes_active_slot(isolated_config):
    """Plain login keeps overwriting the active slot (the singleton)."""
    result, default_creds, _slot, factory = _run_login([])

    assert result.exit_code == 0, result.output
    factory.assert_not_called()
    default_creds.set_token.assert_called_once()
    assert isolated_config.active_session is None


def test_login_plain_names_the_active_session(isolated_config):
    """A plain re-login into a named active slot says which one."""
    isolated_config.active_session = "work"
    result, _default, _slot, _factory = _run_login([])

    assert result.exit_code == 0, result.output
    assert "Session: work" in result.output


# --- logout --as / --all ------------------------------------------------------


def _slot_mock(token="tok-slot"):
    slot = mock.Mock()
    slot.get_token.return_value = token
    slot.get_refresh_token.return_value = None
    slot.get_token_auth_url.return_value = "https://auth.example.com/auth/v1"
    slot.get_login_session_id.return_value = None
    return slot


def test_logout_as_removes_slot_and_resets_active(isolated_config):
    """--as logs out that slot, unlists it, and clears an active pointer."""
    isolated_config.active_session = "work"
    isolated_config.add_session("work")
    isolated_config.add_session("agent")
    slot = _slot_mock()
    with (
        mock.patch(
            "campus_cli.auth.login.session_storage", return_value=slot
        ),
        mock.patch(
            "campus_cli.auth.login.credentials", mock.Mock()
        ),
        mock.patch("campus_cli.auth.login.revoke_token", return_value=True),
    ):
        result = runner.invoke(app, ["auth", "logout", "--as", "work", "-y"])

    assert result.exit_code == 0, result.output
    slot.delete_token.assert_called_once()
    assert isolated_config.get_sessions() == ["agent"]
    assert isolated_config.active_session is None
    assert "Logged out session 'work'" in result.output


def test_logout_as_keeps_other_slots(isolated_config):
    """--as never touches the default slot or other named slots."""
    isolated_config.add_session("work")
    slot = _slot_mock()
    default_creds = mock.Mock()
    default_creds.get_token.return_value = "tok-default"
    with (
        mock.patch(
            "campus_cli.auth.login.session_storage", return_value=slot
        ),
        mock.patch("campus_cli.auth.login.credentials", default_creds),
        mock.patch("campus_cli.auth.login.revoke_token", return_value=True),
    ):
        result = runner.invoke(app, ["auth", "logout", "--as", "work", "-y"])

    assert result.exit_code == 0, result.output
    default_creds.delete_token.assert_not_called()
    assert isolated_config.active_session is None


def test_logout_all_clears_every_slot(isolated_config):
    """--all logs out the default slot and every named session (#113).

    The batch addresses slots through session_storage (the singleton is
    bound to the active slot, which --all must not privilege).
    """
    isolated_config.add_session("work")
    isolated_config.add_session("agent")
    isolated_config.active_session = "work"
    slots = {None: _slot_mock(), "work": _slot_mock(), "agent": _slot_mock()}
    with (
        mock.patch(
            "campus_cli.auth.login.session_storage",
            side_effect=lambda name: slots[name],
        ),
        mock.patch("campus_cli.auth.login.revoke_token", return_value=True),
    ):
        result = runner.invoke(app, ["auth", "logout", "--all", "-y"])

    assert result.exit_code == 0, result.output
    for slot in slots.values():
        slot.delete_token.assert_called_once()
    assert isolated_config.get_sessions() == []
    assert isolated_config.active_session is None
    assert "Logged out 3 session(s)." in result.output


def test_logout_as_and_all_are_mutually_exclusive():
    result = runner.invoke(app, ["auth", "logout", "--as", "work", "--all", "-y"])

    assert result.exit_code == 1, result.output
    assert "not both" in result.stderr


def test_logout_default_targets_the_active_slot(isolated_config):
    """Plain logout clears the active slot and resets the pointer."""
    isolated_config.active_session = "work"
    isolated_config.add_session("work")
    default_creds = _slot_mock()
    with (
        mock.patch("campus_cli.auth.login.credentials", default_creds),
        mock.patch("campus_cli.auth.login.revoke_token", return_value=True),
    ):
        result = runner.invoke(app, ["auth", "logout", "-y"])

    assert result.exit_code == 0, result.output
    default_creds.delete_token.assert_called_once()
    assert isolated_config.get_sessions() == []
    assert isolated_config.active_session is None


# --- use ----------------------------------------------------------------------


def _use_store(slot):
    """Store mock for `use` tests: 'work' logged in, everything else empty."""
    store = mock.Mock()
    if slot == "work":
        store.get_token.return_value = "tok-work"
        store.get_token_user_id.return_value = "user-alice@example.com"
        store.get_token_auth_url.return_value = "https://auth.example.com/auth/v1"
        store.get_token_scopes.return_value = ["read"]
        store.get_token_expires_at.return_value = (
            "2026-12-01T00:00:00+00:00"
        )
        store.is_token_expired.return_value = False
    else:
        store.get_token.return_value = None
    return store


def test_use_switches_to_known_session(isolated_config):
    isolated_config.add_session("work")
    with mock.patch(
        "campus_cli.auth.login.session_storage",
        side_effect=lambda slot: _use_store(slot),
    ):
        result = runner.invoke(app, ["auth", "use", "work"])

    assert result.exit_code == 0, result.output
    assert isolated_config.active_session == "work"
    assert "Switched to session 'work'" in result.output
    assert "user-alice@example.com" in result.output


def test_use_lists_sessions(isolated_config):
    isolated_config.add_session("work")
    isolated_config.active_session = "work"
    with mock.patch(
        "campus_cli.auth.login.session_storage",
        side_effect=lambda slot: _use_store(slot),
    ):
        result = runner.invoke(app, ["auth", "use"])

    assert result.exit_code == 0, result.output
    assert "default" in result.output
    assert "work" in result.output
    assert "(active)" in result.output


def test_use_unknown_session_fails_with_login_hint():
    with mock.patch(
        "campus_cli.auth.login.session_storage",
        side_effect=lambda slot: _use_store(slot),
    ):
        result = runner.invoke(app, ["auth", "use", "ghost"])

    assert result.exit_code == 1, result.output
    assert "No stored session 'ghost'" in result.stderr
    assert "campus auth login --as ghost" in result.stderr


def test_use_default_clears_the_pointer(isolated_config):
    isolated_config.active_session = "work"
    result = runner.invoke(app, ["auth", "use", "--default"])

    assert result.exit_code == 0, result.output
    assert isolated_config.active_session is None


def test_use_name_and_default_are_mutually_exclusive():
    result = runner.invoke(app, ["auth", "use", "work", "--default"])

    assert result.exit_code == 1, result.output
    assert "not both" in result.stderr


def test_use_rejects_invalid_name():
    result = runner.invoke(app, ["auth", "use", "bad name"])

    assert result.exit_code == 1, result.output
    assert "Session names" in result.stderr


# --- status --all ---------------------------------------------------------------


def test_status_all_inventories_slots(isolated_config):
    """--all lists every slot offline, marking the active one."""
    isolated_config.add_session("work")
    isolated_config.active_session = "work"
    with mock.patch(
        "campus_cli.auth.status.session_storage",
        side_effect=lambda slot: _use_store(slot),
    ):
        result = runner.invoke(app, ["auth", "status", "--all"])

    assert result.exit_code == 0, result.output
    assert "Session default" in result.output
    assert "Session work (active)" in result.output
    assert "user-alice@example.com" in result.output
    assert "no stored credentials" in result.output


def test_status_all_json_shape(isolated_config):
    """--all --json emits one summary object per slot."""
    isolated_config.add_session("work")
    with mock.patch(
        "campus_cli.auth.status.session_storage",
        side_effect=lambda slot: _use_store(slot),
    ):
        result = runner.invoke(app, ["auth", "status", "--all", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert [entry["session"] for entry in payload] == ["default", "work"]
    by_name = {entry["session"]: entry for entry in payload}
    assert by_name["default"]["authenticated"] is False
    assert by_name["work"]["authenticated"] is True
    assert by_name["work"]["user_id"] == "user-alice@example.com"
    assert by_name["work"]["active"] is False


def test_status_all_exit_code_when_nothing_stored():
    with mock.patch(
        "campus_cli.auth.status.session_storage",
        side_effect=lambda slot: _use_store(slot),
    ):
        result = runner.invoke(app, ["auth", "status", "--all"])

    assert result.exit_code == 1, result.output

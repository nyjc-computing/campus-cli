"""Unit tests for circle-membership commands (campus#1202).

Covers the gate-parity probe (campus circle members check) and the
inverted roles listing (campus circle roles): helper rendering,
name→ID resolution, and command wiring against a mocked API client.
"""

import pytest
from typer.testing import CliRunner

from campus_cli.resources.circles import (
    _format_resolution,
    _resolve_circle_id,
    circle_app,
)

runner = CliRunner()


def _resolution(**overrides):
    fields = {
        "member_id": "teacher@campus.test",
        "access_value": 15,
        "direct": False,
        "via": ["timetable-staff"],
    }
    fields.update(overrides)
    return fields


class _FakeApi:
    """Minimal stand-in for CampusClient (list + subscript + users)."""

    def __init__(self, circles, members, roles_body):
        self._circles = circles
        self._members = members
        self.api_users = type("Users", (), {})()
        self.api_users.roles = lambda user_id: roles_body

        class Circles:
            def list(self_inner):
                return circles

            def __getitem__(self_inner, key):
                return type("Circle", (), {"members": members})()

        self.api_circles = Circles()


def _circle(name, id_):
    return type("C", (), {"name": name, "id": id_})()


class TestFormatResolution:
    """_format_resolution renders the resolution detail suffix."""

    def test_via_chain(self):
        assert (
            _format_resolution(_resolution())
            == "access 15, via timetable-staff"
        )

    def test_nested_via_chain(self):
        assert _format_resolution(_resolution(via=["staff", "teachers"])) == (
            "access 15, via staff › teachers"
        )

    def test_direct_edge(self):
        assert (
            _format_resolution(_resolution(direct=True, via=[]))
            == "access 15, direct"
        )


class TestResolveCircleId:
    """_resolve_circle_id resolves exact names, passes IDs through."""

    def test_exact_name_match(self):
        api = _FakeApi([_circle("timetable.admin", "c1")], None, {})
        assert _resolve_circle_id(api, "timetable.admin") == "c1"

    def test_unknown_name_passes_through_as_id(self):
        api = _FakeApi([], None, {})
        assert _resolve_circle_id(api, "uid-circle-abc") == "uid-circle-abc"


class TestMembersCheckCommand:
    """campus circle members check drives the shared resolver."""

    @pytest.fixture
    def members(self, monkeypatch):
        members = type("Members", (), {})()
        members.calls = []
        members.answer = _resolution()

        def resolve(member_id, *, transitive=True):
            members.calls.append((member_id, transitive))
            return members.answer

        members.resolve = resolve
        api = _FakeApi(
            [_circle("timetable.admin", "c1")], members,
            {"user_id": "x", "roles": []},
        )
        monkeypatch.setattr(
            "campus_cli.resources.circles.get_api_client", lambda: api
        )
        return members

    def test_transitive_by_default_with_name_resolution(self, members):
        result = runner.invoke(
            circle_app,
            ["members", "check", "--circle-id", "timetable.admin",
             "--member-id", "t@c"],
        )
        assert result.exit_code == 0
        assert members.calls == [("t@c", True)]
        assert "member" in result.output
        assert "via timetable-staff" in result.output

    def test_direct_flag_limits_probe(self, members):
        result = runner.invoke(
            circle_app,
            ["members", "check", "--circle-id", "c1",
             "--member-id", "t@c", "--direct"],
        )
        assert result.exit_code == 0
        assert members.calls == [("t@c", False)]

    def test_not_a_member_is_not_an_error(self, members):
        members.answer = None
        result = runner.invoke(
            circle_app,
            ["members", "check", "--circle-id", "c1", "--member-id", "x@c"],
        )
        assert result.exit_code == 0
        assert "not a member" in result.output

    def test_json_output_carries_resolution(self, members):
        result = runner.invoke(
            circle_app,
            ["members", "check", "--circle-id", "c1",
             "--member-id", "t@c", "--json"],
        )
        assert result.exit_code == 0
        assert '"resolution"' in result.output

    def test_dry_run_prints_python_api(self, members):
        result = runner.invoke(
            circle_app,
            ["members", "check", "--circle-id", "c1",
             "--member-id", "t@c", "--dry-run"],
        )
        assert result.exit_code == 0
        assert "members.resolve" in result.output
        assert members.calls == []


class TestRolesCommand:
    """campus circle roles drives the inverted check."""

    @pytest.fixture
    def roles_body(self, monkeypatch):
        roles_body = {
            "user_id": "t@c",
            "roles": [
                {
                    "circle_id": "c1",
                    "name": "timetable.admin",
                    "access_value": 15,
                    "direct": False,
                    "via": ["staff"],
                }
            ],
        }
        api = _FakeApi([], None, roles_body)
        monkeypatch.setattr(
            "campus_cli.resources.circles.get_api_client", lambda: api
        )
        return roles_body

    def test_lists_roles(self, roles_body):
        result = runner.invoke(circle_app, ["roles", "--user-id", "t@c"])
        assert result.exit_code == 0
        assert "timetable.admin" in result.output
        assert "via staff" in result.output

    def test_empty_roles_is_not_an_error(self, roles_body, monkeypatch):
        roles_body["roles"] = []
        result = runner.invoke(circle_app, ["roles", "--user-id", "t@c"])
        assert result.exit_code == 0
        assert "no roles" in result.output

    def test_json_output(self, roles_body):
        result = runner.invoke(
            circle_app, ["roles", "--user-id", "t@c", "--json"]
        )
        assert result.exit_code == 0
        assert '"roles"' in result.output

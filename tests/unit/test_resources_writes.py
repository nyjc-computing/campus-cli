"""Unit tests for campus.api resource write commands (#4 Phase B)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


def _assignment(**overrides):
    fields = {
        "id": "uid-assignment-1",
        "title": "Quiz 1",
        "description": "First quiz",
        "created_by": "teacher@school.edu",
        "created_at": "2026-11-01T00:00:00+00:00",
        "updated_at": None,
        "questions": [],
        "classroom_links": [],
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _circle(**overrides):
    fields = {
        "id": "uid-circle-1",
        "name": "13A2",
        "description": "Class circle",
        "tag": "class",
        "created_at": "2026-01-01T00:00:00+00:00",
        "members": {},
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _submission(**overrides):
    fields = {
        "id": "uid-submission-1",
        "assignment_id": "uid-assignment-1",
        "student_id": "student@school.edu",
        "course_id": None,
        "submitted_at": None,
        "created_at": "2026-11-02T00:00:00+00:00",
        "updated_at": None,
        "responses": [],
        "feedback": [],
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_assignment_new_and_update():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        api = MagicMock()
        api.api_assignments.new.return_value = _assignment(title="New quiz")
        api.api_assignments["uid-assignment-1"].get.return_value = _assignment(
            title="Updated"
        )
        mock_get.return_value = api
        result = runner.invoke(app, [
            "assignment", "new", "--title", "New quiz",
            "--description", "d", "--json",
        ])
        assert result.exit_code == 0, result.stdout
        assert api.api_assignments.new.call_args.kwargs == {
            "title": "New quiz", "description": "d"
        }
        assert json.loads(result.stdout)["title"] == "New quiz"

        result = runner.invoke(app, [
            "assignment", "update", "--assignment-id", "uid-assignment-1",
            "--title", "Updated",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_assignments["uid-assignment-1"].update.assert_called_once_with(
            title="Updated"
        )


def test_assignment_update_requires_a_field():
    with patch("campus_cli.resources.assignments.get_api_client"):
        result = runner.invoke(
            app, ["assignment", "update", "--assignment-id", "a1"]
        )
    assert result.exit_code == 1
    assert "--title" in result.stderr


def test_assignment_delete_confirm_gate():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(
            app, ["assignment", "delete", "--assignment-id", "a1"]
        )
        assert result.exit_code == 1
        api.api_assignments["a1"].delete.assert_not_called()
        result = runner.invoke(
            app, ["assignment", "delete", "--assignment-id", "a1", "-y"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_assignments["a1"].delete.assert_called_once_with()


def test_assignment_links_add():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(app, [
            "assignment", "links", "add", "--assignment-id", "a1",
            "--course-id", "c1", "--coursework-id", "cw1",
            "--attachment-id", "at1",
        ])
    assert result.exit_code == 0, result.stdout
    api.api_assignments["a1"].links.add.assert_called_once_with(
        course_id="c1", coursework_id="cw1", attachment_id="at1"
    )


def test_assignment_new_dry_run_never_touches_api():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        result = runner.invoke(app, [
            "assignment", "new", "--title", "T", "--description", "d",
            "--dry-run",
        ])
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "assignments.new(" in result.stdout
    assert "title='T'" in result.stdout


def test_circle_new_update_delete():
    with patch("campus_cli.resources.circles.get_api_client") as mock_get:
        api = MagicMock()
        api.api_circles.new.return_value = _circle(name="Probes")
        mock_get.return_value = api
        result = runner.invoke(app, [
            "circle", "new", "--name", "Probes", "--tag", "probe",
            "--description", "d",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_circles.new.assert_called_once_with(
            name="Probes", tag="probe", description="d"
        )
        result = runner.invoke(app, [
            "circle", "update", "--circle-id", "uid-circle-1",
            "--name", "Renamed", "--description", "nd",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_circles["uid-circle-1"].update.assert_called_once_with(
            name="Renamed", description="nd"
        )
        result = runner.invoke(
            app, ["circle", "delete", "--circle-id", "uid-circle-1", "-y"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_circles["uid-circle-1"].delete.assert_called_once_with()


def test_circle_members_add_set_remove():
    with patch("campus_cli.resources.circles.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(app, [
            "circle", "members", "add", "--circle-id", "c1",
            "--member-id", "m1", "--access", "3",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_circles["c1"].members.add.assert_called_once_with("m1", 3)
        result = runner.invoke(app, [
            "circle", "members", "set", "--circle-id", "c1",
            "--member-id", "m1", "--access", "5",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_circles["c1"].members.set.assert_called_once_with("m1", 5)
        result = runner.invoke(app, [
            "circle", "members", "remove", "--circle-id", "c1",
            "--member-id", "m1", "-y",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_circles["c1"].members.remove.assert_called_once_with("m1")


def test_circle_members_remove_confirm_gate():
    with patch("campus_cli.resources.circles.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(app, [
            "circle", "members", "remove", "--circle-id", "c1",
            "--member-id", "m1",
        ])
    assert result.exit_code == 1
    api.api_circles["c1"].members.remove.assert_not_called()


def test_timetable_set_current_next_and_metadata():
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        api = MagicMock()
        api.api_timetables.patch.return_value = {
            "current": "t1", "next": None, "effective_from": None,
        }
        mock_get.return_value = api
        result = runner.invoke(
            app, ["timetable", "patch", "--current", "t1", "-y"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_timetables.patch.assert_called_once_with(current="t1")
        result = runner.invoke(app, [
            "timetable", "patch", "--next", "t2",
            "--effective-from", "2027-06-01", "-y",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_timetables.patch.assert_called_with(
            next="t2", effective_from="2027-06-01"
        )
        result = runner.invoke(app, [
            "timetable", "metadata", "update", "--timetable-id", "t1",
            "--start-date", "2027-01-01", "--end-date", "2027-06-01",
        ])
        assert result.exit_code == 0, result.stdout
        (api.api_timetables["t1"].metadata.update
         .assert_called_once_with(start_date="2027-01-01",
                                  end_date="2027-06-01"))


def test_timetable_set_current_confirm_gate():
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(
            app, ["timetable", "patch", "--current", "t1"]
        )
    assert result.exit_code == 1
    api.api_timetables.patch.assert_not_called()


def test_timetable_cancel_next_and_rejects_combinations():
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        api = MagicMock()
        api.api_timetables.cancel_next.return_value = {
            "current": "t1", "next": None, "effective_from": None,
        }
        mock_get.return_value = api
        result = runner.invoke(
            app, ["timetable", "patch", "--cancel-next", "-y"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_timetables.cancel_next.assert_called_once_with()
        both = runner.invoke(app, [
            "timetable", "patch", "--current", "t1",
            "--next", "t2", "-y",
        ])
        assert both.exit_code == 1


def test_submission_update_submit_unsubmit():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        api = MagicMock()
        api.api_submissions["uid-submission-1"].get.return_value = _submission(
            submitted_at="2026-11-06T00:00:00+00:00"
        )
        mock_get.return_value = api
        result = runner.invoke(app, [
            "submission", "update", "--submission-id", "uid-submission-1",
            "--submitted-at", "2026-11-06T00:00:00+00:00", "--json",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_submissions["uid-submission-1"].update.assert_called_once_with(
            submitted_at="2026-11-06T00:00:00+00:00"
        )
        result = runner.invoke(
            app, ["submission", "submit", "--submission-id", "uid-submission-1"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_submissions["uid-submission-1"].submit.assert_called_once_with()
        result = runner.invoke(
            app,
            ["submission", "unsubmit", "--submission-id", "uid-submission-1"],
        )
        assert result.exit_code == 0, result.stdout
        (api.api_submissions["uid-submission-1"].unsubmit
         .assert_called_once_with())


def test_submission_update_requires_submitted_at():
    with patch("campus_cli.resources.submissions.get_api_client"):
        result = runner.invoke(
            app, ["submission", "update", "--submission-id", "s1"]
        )
    assert result.exit_code == 1

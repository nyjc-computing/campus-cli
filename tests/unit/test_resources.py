"""Unit tests for campus.api resource read commands (#4 Phase A)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


# --- model fixtures -------------------------------------------------------

def _assignment(**overrides):
    fields = {
        "id": "uid-assignment-1",
        "title": "Quiz 1",
        "description": "First quiz",
        "created_by": "teacher@school.edu",
        "created_at": "2026-11-01T00:00:00+00:00",
        "updated_at": None,
        "questions": [{"id": "q1"}],
        "classroom_links": [],
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


def _meta(**overrides):
    fields = {
        "id": "uid-timetable-1",
        "filename": "t1.json",
        "start_date": "2026-01-01",
        "end_date": "2026-06-01",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _entry(**overrides):
    fields = {
        "id": "uid-entry-1",
        "lessongroup_id": "lg1",
        "venue": "B3-04",
        "weekday": 2,
        "timeslot": 5,
        "label": "Computing",
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
        "members": {"student@school.edu": 1},
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _timetable_full():
    t = _meta()
    return SimpleNamespace(
        **{
            **t.__dict__,
            "entries": [_entry()],
            "to_resource": lambda: {"id": t.id, "entries": []},
        }
    )


# --- assignment -----------------------------------------------------------

def test_assignment_list_table():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        api = MagicMock()
        api.api_assignments.list.return_value = [_assignment()]
        mock_get.return_value = api
        result = runner.invoke(app, ["assignment", "list"])
    assert result.exit_code == 0, result.stdout
    assert "Quiz 1" in result.stdout
    assert "teacher@school.edu" in result.stdout


def test_assignment_list_json_and_created_by_filter():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        api = MagicMock()
        api.api_assignments.list.return_value = [_assignment()]
        mock_get.return_value = api
        result = runner.invoke(
            app, ["assignment", "list", "--json", "--created-by",
                  "teacher@school.edu"]
        )
    assert result.exit_code == 0, result.stdout
    assert api.api_assignments.list.call_args.kwargs == {
        "created_by": "teacher@school.edu"
    }
    rows = json.loads(result.stdout)
    assert rows[0]["id"] == "uid-assignment-1"
    assert rows[0]["questions"] == [{"id": "q1"}]


def test_assignment_list_empty():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        api = MagicMock()
        api.api_assignments.list.return_value = []
        mock_get.return_value = api
        result = runner.invoke(app, ["assignment", "list"])
    assert result.exit_code == 0, result.stdout
    assert "No assignments found." in result.stdout


def test_assignment_get_detail_and_json():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        api = MagicMock()
        api.api_assignments["uid-assignment-1"].get.return_value = _assignment()
        mock_get.return_value = api
        result = runner.invoke(
            app, ["assignment", "get", "--assignment-id", "uid-assignment-1"]
        )
        assert result.exit_code == 0, result.stdout
        assert "First quiz" in result.stdout
        result = runner.invoke(
            app, ["assignment", "get", "--assignment-id", "uid-assignment-1",
                  "--json"]
        )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["created_by"] == "teacher@school.edu"


def test_assignment_dry_run_never_touches_api():
    with patch("campus_cli.resources.assignments.get_api_client") as mock_get:
        result = runner.invoke(
            app, ["assignment", "list", "--created-by", "x@school.edu",
                  "--dry-run"]
        )
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "campus.api.assignments.list(" in result.stdout
    assert "created_by='x@school.edu'" in result.stdout
    # The api service authenticates the bearer on its own client (#4)
    assert 'campus.api.client.set_bearer_authorization' in result.stdout


# --- submission -----------------------------------------------------------

def test_submission_list_with_filters():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        api = MagicMock()
        api.api_submissions.list.return_value = [
            _submission(submitted_at="2026-11-03T01:00:00+00:00")
        ]
        mock_get.return_value = api
        result = runner.invoke(app, [
            "submission", "list", "--assignment-id", "uid-assignment-1",
            "--student-id", "student@school.edu", "--json",
        ])
    assert result.exit_code == 0, result.stdout
    kwargs = api.api_submissions.list.call_args.kwargs
    assert kwargs["assignment_id"] == "uid-assignment-1"
    assert kwargs["student_id"] == "student@school.edu"
    assert kwargs["course_id"] is None
    assert json.loads(result.stdout)[0]["submitted_at"].startswith("2026-11-03")


def test_submission_by_assignment_and_by_student():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        api = MagicMock()
        api.api_submissions.by_assignment.return_value = [_submission()]
        api.api_submissions.by_student.return_value = [_submission()]
        mock_get.return_value = api
        result = runner.invoke(
            app, ["submission", "by-assignment", "--assignment-id", "a1"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_submissions.by_assignment.assert_called_once_with("a1")
        result = runner.invoke(
            app, ["submission", "by-student", "--student-id", "s1", "--json"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_submissions.by_student.assert_called_once_with("s1")
        assert json.loads(result.stdout)[0]["assignment_id"] == "uid-assignment-1"


def test_submission_get_shows_state():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        api = MagicMock()
        api.api_submissions["uid-submission-1"].get.return_value = _submission()
        mock_get.return_value = api
        result = runner.invoke(
            app, ["submission", "get", "--submission-id", "uid-submission-1"]
        )
    assert result.exit_code == 0, result.stdout
    assert "not submitted" in result.stdout


def test_submission_dry_run_by_assignment():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        result = runner.invoke(
            app, ["submission", "by-assignment", "--assignment-id", "a1",
                  "--dry-run"]
        )
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "by_assignment('a1')" in result.stdout


# --- timetable ------------------------------------------------------------

def test_timetable_list_and_current_next():
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        api = MagicMock()
        api.api_timetables.list.return_value = [_meta()]
        api.api_timetables.get_current.return_value = "uid-timetable-1"
        api.api_timetables.get_next.return_value = "uid-timetable-2"
        mock_get.return_value = api
        result = runner.invoke(app, ["timetable", "list", "--json"])
        assert result.exit_code == 0, result.stdout
        assert json.loads(result.stdout)[0]["filename"] == "t1.json"
        result = runner.invoke(app, ["timetable", "current"])
        assert result.exit_code == 0, result.stdout
        assert "uid-timetable-1" in result.stdout
        result = runner.invoke(app, ["timetable", "next", "--json"])
        assert result.exit_code == 0, result.stdout
        assert json.loads(result.stdout) == {"next": "uid-timetable-2"}


def test_timetable_get_and_entries():
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        api = MagicMock()
        api.api_timetables["uid-timetable-1"].get.return_value = _timetable_full()
        api.api_timetables["uid-timetable-1"].entries.list.return_value = [
            _entry()
        ]
        mock_get.return_value = api
        result = runner.invoke(
            app, ["timetable", "get", "--timetable-id", "uid-timetable-1"]
        )
        assert result.exit_code == 0, result.stdout
        assert "Entries: 1" in result.stdout
        result = runner.invoke(
            app, ["timetable", "entries", "--timetable-id", "uid-timetable-1"]
        )
        assert result.exit_code == 0, result.stdout
        assert "B3-04" in result.stdout
        assert "Computing" in result.stdout


def test_timetable_dry_run_entries():
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        result = runner.invoke(
            app, ["timetable", "entries", "--timetable-id", "t1", "--dry-run"]
        )
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "entries.list()" in result.stdout


# --- circle ---------------------------------------------------------------

def test_circle_list_and_get():
    with patch("campus_cli.resources.circles.get_api_client") as mock_get:
        api = MagicMock()
        api.api_circles.list.return_value = [_circle()]
        api.api_circles["uid-circle-1"].get.return_value = _circle()
        mock_get.return_value = api
        result = runner.invoke(app, ["circle", "list", "--json"])
        assert result.exit_code == 0, result.stdout
        rows = json.loads(result.stdout)
        assert rows[0]["member_count"] == 1
        result = runner.invoke(app, ["circle", "get", "--circle-id", "c1"])
        assert result.exit_code == 0, result.stdout
        assert "13A2" in result.stdout
        assert "Class circle" in result.stdout


def test_circle_members_list():
    with patch("campus_cli.resources.circles.get_api_client") as mock_get:
        api = MagicMock()
        api.api_circles["uid-circle-1"].members.list.return_value = {
            "student@school.edu": 1
        }
        mock_get.return_value = api
        result = runner.invoke(
            app, ["circle", "members", "list", "--circle-id", "uid-circle-1"]
        )
        assert result.exit_code == 0, result.stdout
        assert "student@school.edu" in result.stdout
        result = runner.invoke(
            app, ["circle", "members", "list", "--circle-id", "uid-circle-1",
                  "--json"]
        )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == {"student@school.edu": 1}


def test_circle_dry_run_members():
    with patch("campus_cli.resources.circles.get_api_client") as mock_get:
        result = runner.invoke(
            app, ["circle", "members", "list", "--circle-id", "c1", "--dry-run"]
        )
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "members.list()" in result.stdout

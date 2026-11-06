"""Unit tests for Phase C structured-payload commands (#4)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


# --- timetable new --------------------------------------------------------

def test_timetable_new_passes_payloads(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text('{"lessongroups": [{"id": "lg1"}]}', encoding="utf-8")
    meta = '{"start_date": "2027-01-01", "end_date": "2027-06-01"}'
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        api = MagicMock()
        api.api_timetables.new.return_value = {"id": "uid-timetable-9"}
        mock_get.return_value = api
        result = runner.invoke(app, [
            "timetable", "new", "--metadata", meta,
            "--data-file", str(data_file), "--json",
        ])
    assert result.exit_code == 0, result.stdout
    kwargs = api.api_timetables.new.call_args.kwargs
    assert kwargs["metadata"] == {
        "start_date": "2027-01-01", "end_date": "2027-06-01"
    }
    assert kwargs["data"] == {"lessongroups": [{"id": "lg1"}]}
    assert json.loads(result.stdout)["id"] == "uid-timetable-9"


def test_timetable_new_rejects_lesson_groups(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text('{"lesson_groups": []}', encoding="utf-8")
    with patch("campus_cli.resources.timetables.get_api_client"):
        result = runner.invoke(app, [
            "timetable", "new", "--metadata", "{}",
            "--data-file", str(data_file),
        ])
    assert result.exit_code == 1
    assert "lessongroups" in result.stderr
    assert "rename" in result.stderr


def test_timetable_new_rejects_bad_metadata_json(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text('{"lessongroups": []}', encoding="utf-8")
    with patch("campus_cli.resources.timetables.get_api_client"):
        result = runner.invoke(app, [
            "timetable", "new", "--metadata", "not-json",
            "--data-file", str(data_file),
        ])
    assert result.exit_code == 1
    assert "--metadata" in result.stderr


def test_timetable_new_requires_missing_data_file(tmp_path):
    with patch("campus_cli.resources.timetables.get_api_client"):
        result = runner.invoke(app, [
            "timetable", "new", "--metadata", "{}",
            "--data-file", str(tmp_path / "nope.json"),
        ])
    assert result.exit_code == 1
    assert "not found" in result.stderr


def test_timetable_new_dry_run_never_touches_api(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text('{"lessongroups": [1, 2]}', encoding="utf-8")
    with patch("campus_cli.resources.timetables.get_api_client") as mock_get:
        result = runner.invoke(app, [
            "timetable", "new", "--metadata", '{"start_date": "2027-01-01"}',
            "--data-file", str(data_file), "--dry-run",
        ])
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "timetable.new(" in result.stdout
    assert "[2 groups from" in result.stdout


# --- submission new -------------------------------------------------------

def test_submission_new_kwargs():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        api = MagicMock()
        api.api_submissions.new.return_value = MagicMock(
            id="uid-submission-9",
            assignment_id="a1",
            student_id="s1",
            course_id="c1",
            submitted_at=None,
            created_at=None,
            updated_at=None,
            responses=[],
            feedback=[],
        )
        mock_get.return_value = api
        result = runner.invoke(app, [
            "submission", "new", "--assignment-id", "a1",
            "--student-id", "s1", "--course-id", "c1",
        ])
    assert result.exit_code == 0, result.stdout
    assert api.api_submissions.new.call_args.kwargs == {
        "assignment_id": "a1",
        "student_id": "s1",
        "course_id": "c1",
        "responses": None,
    }


def test_submission_new_with_responses_json():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        api = MagicMock()
        api.api_submissions.new.return_value = MagicMock(
            id="s9", assignment_id="a1", student_id="s1", course_id="c1",
            submitted_at=None, created_at=None, updated_at=None,
            responses=[{"question_id": "q1", "response_text": "42"}],
            feedback=[],
        )
        mock_get.return_value = api
        result = runner.invoke(app, [
            "submission", "new", "--assignment-id", "a1",
            "--student-id", "s1", "--course-id", "c1",
            "--responses-json", '[{"question_id": "q1", "response_text": "42"}]',
            "--json",
        ])
    assert result.exit_code == 0, result.stdout
    assert (api.api_submissions.new.call_args.kwargs["responses"]
            == [{"question_id": "q1", "response_text": "42"}])
    assert json.loads(result.stdout)["responses"][0]["question_id"] == "q1"


def test_submission_new_rejects_bad_responses_json():
    with patch("campus_cli.resources.submissions.get_api_client"):
        result = runner.invoke(app, [
            "submission", "new", "--assignment-id", "a1",
            "--student-id", "s1", "--course-id", "c1",
            "--responses-json", "not-json",
        ])
    assert result.exit_code == 1
    assert "--responses-json" in result.stderr


def test_submission_new_dry_run_never_touches_api():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        result = runner.invoke(app, [
            "submission", "new", "--assignment-id", "a1",
            "--student-id", "s1", "--course-id", "c1", "--dry-run",
        ])
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "submissions.new(" in result.stdout


# --- responses / feedback add --------------------------------------------

def test_responses_add_and_feedback_add():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(app, [
            "submission", "responses", "add", "--submission-id", "s1",
            "--question-id", "q1", "--response-text", "42",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_submissions["s1"].responses.add.assert_called_once_with(
            question_id="q1", response_text="42"
        )
        result = runner.invoke(app, [
            "submission", "feedback", "add", "--submission-id", "s1",
            "--question-id", "q1", "--feedback-text", "Well done",
        ])
        assert result.exit_code == 0, result.stdout
        api.api_submissions["s1"].feedback.add.assert_called_once_with(
            question_id="q1", feedback_text="Well done"
        )


def test_responses_add_dry_run_never_touches_api():
    with patch("campus_cli.resources.submissions.get_api_client") as mock_get:
        result = runner.invoke(app, [
            "submission", "responses", "add", "--submission-id", "s1",
            "--question-id", "q1", "--response-text", "42", "--dry-run",
        ])
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "responses.add(" in result.stdout

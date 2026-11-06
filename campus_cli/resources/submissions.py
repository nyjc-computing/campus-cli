"""Submission commands (campus-cli#4 Phases A and C)."""

import json

import typer
from rich.console import Console

from campus_cli.auth.common import dry_run_option, get_api_client
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_success,
    print_table,
)

submission_app = typer.Typer(help="Submission commands (campus.api)")
console = Console()

responses_app = typer.Typer(help="Submission responses")
submission_app.add_typer(responses_app, name="responses")

feedback_app = typer.Typer(help="Submission feedback")
submission_app.add_typer(feedback_app, name="feedback")


def _iso(value):
    """Render datetimes as ISO strings; strings and None pass through."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _format_submission(submission) -> dict:
    """Project a Submission model into display/JSON fields."""
    return {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "student_id": submission.student_id,
        "course_id": submission.course_id,
        "submitted_at": _iso(submission.submitted_at),
        "created_at": _iso(submission.created_at),
        "updated_at": _iso(submission.updated_at),
        "responses": submission.responses or [],
        "feedback": submission.feedback or [],
    }


def _print_submission(s: dict) -> None:
    console.print(f"[bold]ID:[/bold] {s['id']}")
    console.print(f"[bold]Assignment:[/bold] {s['assignment_id']}")
    console.print(f"[bold]Student:[/bold] {s['student_id']}")
    if s["course_id"]:
        console.print(f"[bold]Course:[/bold] {s['course_id']}")
    state = "submitted" if s["submitted_at"] else "[yellow]not submitted[/yellow]"
    console.print(f"[bold]State:[/bold] {state}")
    if s["submitted_at"]:
        console.print(f"[bold]Submitted:[/bold] {s['submitted_at']}")
    console.print(
        f"[bold]Responses:[/bold] {len(s['responses'])} · "
        f"[bold]Feedback:[/bold] {len(s['feedback'])}"
    )


def _print_submission_table(submissions: list[dict]) -> None:
    print_table(
        headers=["ID", "Assignment", "Student", "Submitted"],
        rows=[
            [
                s["id"],
                s["assignment_id"],
                s["student_id"],
                s["submitted_at"] or "-",
            ]
            for s in submissions
        ],
    )


@submission_app.command("list")
def submission_list(
    assignment_id: str | None = typer.Option(
        None, "--assignment-id", help="Filter by assignment"
    ),
    student_id: str | None = typer.Option(
        None, "--student-id", help="Filter by student"
    ),
    course_id: str | None = typer.Option(
        None, "--course-id", help="Filter by Google Classroom course"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List submissions, optionally filtered.

    `by-assignment` / `by-student` are sugar for the single-filter forms.
    """
    if dry_run:
        lines = ["submissions = campus.api.submissions.list("]
        if assignment_id:
            lines.append(f"    assignment_id={assignment_id!r},")
        if student_id:
            lines.append(f"    student_id={student_id!r},")
        if course_id:
            lines.append(f"    course_id={course_id!r},")
        lines += [")", "for s in submissions:", "    print(s.id, s.student_id)"]
        print_python_api("campus submission list", lines)
        return

    try:
        api = get_api_client()
        submissions = api.api_submissions.list(
            assignment_id=assignment_id,
            student_id=student_id,
            course_id=course_id,
        )
        formatted = [_format_submission(s) for s in submissions]

        if output_json:
            print_json(formatted)
        elif not formatted:
            console.print("[dim]No submissions found.[/dim]")
        else:
            console.print(f"[bold]Found {len(formatted)} submission(s):[/bold]\n")
            _print_submission_table(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list submissions: {e}")
        raise typer.Exit(1) from e


@submission_app.command("by-assignment")
def submission_by_assignment(
    assignment_id: str = typer.Option(..., "--assignment-id", help="Assignment ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List submissions for one assignment."""
    if dry_run:
        print_python_api(
            "campus submission by-assignment",
            [
                "submissions = campus.api.submissions.by_assignment("
                f"{assignment_id!r})",
                "for s in submissions:",
                "    print(s.id, s.student_id)",
            ],
        )
        return

    try:
        api = get_api_client()
        submissions = api.api_submissions.by_assignment(assignment_id)
        formatted = [_format_submission(s) for s in submissions]

        if output_json:
            print_json(formatted)
        elif not formatted:
            console.print("[dim]No submissions found.[/dim]")
        else:
            console.print(f"[bold]Found {len(formatted)} submission(s):[/bold]\n")
            _print_submission_table(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(
            f"Failed to list submissions for assignment '{assignment_id}': {e}"
        )
        raise typer.Exit(1) from e


@submission_app.command("by-student")
def submission_by_student(
    student_id: str = typer.Option(..., "--student-id", help="Student ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """List submissions by one student."""
    if dry_run:
        print_python_api(
            "campus submission by-student",
            [
                f"submissions = campus.api.submissions.by_student({student_id!r})",
                "for s in submissions:",
                "    print(s.id, s.assignment_id)",
            ],
        )
        return

    try:
        api = get_api_client()
        submissions = api.api_submissions.by_student(student_id)
        formatted = [_format_submission(s) for s in submissions]

        if output_json:
            print_json(formatted)
        elif not formatted:
            console.print("[dim]No submissions found.[/dim]")
        else:
            console.print(f"[bold]Found {len(formatted)} submission(s):[/bold]\n")
            _print_submission_table(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list submissions by student '{student_id}': {e}")
        raise typer.Exit(1) from e


@submission_app.command("get")
def submission_get(
    submission_id: str = typer.Option(..., "--submission-id", help="Submission ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Show one submission (responses and feedback included via --json)."""
    if dry_run:
        print_python_api(
            "campus submission get",
            [
                f"submission = campus.api.submissions[{submission_id!r}].get()",
                "print(submission.student_id, submission.submitted_at)",
            ],
        )
        return

    try:
        api = get_api_client()
        submission = api.api_submissions[submission_id].get()
        formatted = _format_submission(submission)

        if output_json:
            print_json(formatted)
        else:
            _print_submission(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get submission '{submission_id}': {e}")
        raise typer.Exit(1) from e


@submission_app.command("update")
def submission_update(
    submission_id: str = typer.Option(..., "--submission-id", help="Submission ID"),
    submitted_at: str | None = typer.Option(
        None, "--submitted-at", help="New submitted_at timestamp (ISO)"
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Update a submission's timestamp.

    Bulk responses/feedback edits are structured payloads (Phase C,
    campus-cli#4). To just clear the submitted flag, use
    'campus submission unsubmit'.
    """
    if not submitted_at:
        print_error("Give --submitted-at (or use submit/unsubmit).")
        raise typer.Exit(1)

    if dry_run:
        print_python_api(
            "campus submission update",
            [
                f"submission = campus.api.submissions[{submission_id!r}]",
                f"submission.update(submitted_at={submitted_at!r})",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_submissions[submission_id].update(submitted_at=submitted_at)
        formatted = _format_submission(
            api.api_submissions[submission_id].get()
        )

        if output_json:
            print_json(formatted)
        else:
            print_success(
                f"Submission '{submission_id}' updated:"
                f" submitted_at={formatted['submitted_at']}"
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update submission '{submission_id}': {e}")
        raise typer.Exit(1) from e


@submission_app.command("submit")
def submission_submit(
    submission_id: str = typer.Option(..., "--submission-id", help="Submission ID"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Finalize a submission (server stamps submitted_at)."""
    if dry_run:
        print_python_api(
            "campus submission submit",
            [
                f"submission = campus.api.submissions[{submission_id!r}]",
                "submission.submit()",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_submissions[submission_id].submit()
        print_success(f"Submission '{submission_id}' submitted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to submit submission '{submission_id}': {e}")
        raise typer.Exit(1) from e


@submission_app.command("unsubmit")
def submission_unsubmit(
    submission_id: str = typer.Option(..., "--submission-id", help="Submission ID"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Clear a submission's submitted_at timestamp."""
    if dry_run:
        print_python_api(
            "campus submission unsubmit",
            [
                f"submission = campus.api.submissions[{submission_id!r}]",
                "submission.unsubmit()",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_submissions[submission_id].unsubmit()
        print_success(f"Submission '{submission_id}' unsubmitted.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to unsubmit submission '{submission_id}': {e}")
        raise typer.Exit(1) from e


@submission_app.command("new")
def submission_new(
    assignment_id: str = typer.Option(..., "--assignment-id", help="Assignment ID"),
    student_id: str = typer.Option(..., "--student-id", help="Student user ID"),
    course_id: str = typer.Option(
        ..., "--course-id", help="Google Classroom course ID"
    ),
    responses_json: str | None = typer.Option(
        None, "--responses-json",
        help='Initial responses as inline JSON, e.g. [{"question_id":'
        ' "q1", "response_text": "..."}]'
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """Create a submission for (assignment, student)."""
    responses = None
    if responses_json is not None:
        try:
            responses = json.loads(responses_json)
        except json.JSONDecodeError as e:
            print_error(f"--responses-json is not valid JSON: {e}")
            raise typer.Exit(1) from e
        if not isinstance(responses, list):
            print_error("--responses-json must be a JSON array.")
            raise typer.Exit(1)

    if dry_run:
        new_kwargs = [
            f"    assignment_id={assignment_id!r},",
            f"    student_id={student_id!r},",
            f"    course_id={course_id!r},",
        ]
        if responses is not None:
            new_kwargs.append(f"    responses={responses!r},")
        print_python_api(
            "campus submission new",
            [
                "submission = campus.api.submissions.new(",
                *new_kwargs,
                ")",
                "print(submission.id)",
            ],
        )
        return

    try:
        api = get_api_client()
        submission = api.api_submissions.new(
            assignment_id=assignment_id,
            student_id=student_id,
            course_id=course_id,
            responses=responses,
        )
        formatted = _format_submission(submission)

        if output_json:
            print_json(formatted)
        else:
            print_success(f"Submission created: {formatted['id']}")
            _print_submission(formatted)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create submission: {e}")
        raise typer.Exit(1) from e


@responses_app.command("add")
def responses_add(
    submission_id: str = typer.Option(..., "--submission-id", help="Submission ID"),
    question_id: str = typer.Option(..., "--question-id", help="Question ID"),
    response_text: str = typer.Option(
        ..., "--response-text", help="The student's response text"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """Add or update a response to one question (upsert)."""
    if dry_run:
        print_python_api(
            "campus submission responses add",
            [
                "responses = campus.api.submissions["
                f"{submission_id!r}].responses",
                "responses.add(",
                f"    question_id={question_id!r},",
                f"    response_text={response_text!r},",
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_submissions[submission_id].responses.add(
            question_id=question_id, response_text=response_text
        )
        print_success(
            f"Response to '{question_id}' recorded on submission"
            f" '{submission_id}'."
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(
            f"Failed to add response to submission '{submission_id}': {e}"
        )
        raise typer.Exit(1) from e


@feedback_app.command("add")
def feedback_add(
    submission_id: str = typer.Option(..., "--submission-id", help="Submission ID"),
    question_id: str = typer.Option(..., "--question-id", help="Question ID"),
    feedback_text: str = typer.Option(
        ..., "--feedback-text", help="The teacher's feedback text"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """Add feedback on a response to one question."""
    if dry_run:
        print_python_api(
            "campus submission feedback add",
            [
                "feedback = campus.api.submissions["
                f"{submission_id!r}].feedback",
                "feedback.add(",
                f"    question_id={question_id!r},",
                f"    feedback_text={feedback_text!r},",
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        api.api_submissions[submission_id].feedback.add(
            question_id=question_id, feedback_text=feedback_text
        )
        print_success(
            f"Feedback on '{question_id}' recorded on submission"
            f" '{submission_id}'."
        )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(
            f"Failed to add feedback to submission '{submission_id}': {e}"
        )
        raise typer.Exit(1) from e

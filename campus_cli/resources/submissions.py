"""Submission read commands (campus-cli#4 Phase A)."""

import typer
from rich.console import Console

from campus_cli.auth.common import dry_run_option, get_api_client
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_table,
)

submission_app = typer.Typer(help="Submission commands (campus.api)")
console = Console()


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

"""Campus API resource commands (campus-cli#4).

Read commands over the campus.api service (assignments, submissions,
timetables, circles). Phase A is read-only; Phase B writes ship after
a live write-access check (see issue #4).
"""

from .assignments import assignment_app
from .circles import circle_app
from .files import file_app
from .hostedapps import app_app
from .submissions import submission_app
from .timetables import timetable_app

__all__ = [
    "app_app",
    "assignment_app",
    "circle_app",
    "file_app",
    "submission_app",
    "timetable_app",
]

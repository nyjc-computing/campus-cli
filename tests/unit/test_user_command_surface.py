"""The user command surfaces must not drift (#1226 follow-up).

The v0.10.0 cut dropped `campus user get` (the trim partitioned the
module at the wrong command) and nothing failed — so pin both groups'
command sets explicitly: the facade group is read-only list/get; the
management group carries the full CRUD set.
"""

import unittest

from campus_cli.auth.manage_user import manage_user_app
from campus_cli.auth.user import user_app


def _command_names(app) -> set[str]:
    return {command.name for command in app.registered_commands}


class TestUserCommandSurface(unittest.TestCase):
    def test_facade_group_is_read_only_list_get(self):
        self.assertEqual(_command_names(user_app), {"list", "get"})

    def test_management_group_carries_full_crud(self):
        self.assertEqual(
            _command_names(manage_user_app),
            {"list", "get", "new", "activate", "edit", "delete"},
        )


if __name__ == "__main__":
    unittest.main()

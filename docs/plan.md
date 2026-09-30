# Implementation Plan

## Project Status

**Last Updated:** 2026-09-30

### Completed
- ✅ Phase 1: Core Infrastructure (CLI entry point, credentials, config, output formatting)
- ✅ Phase 2: Authentication (OAuth device flow via public `guest` client, logout, token storage, auto-refresh)
- ✅ Phase 3: OAuth Client Commands (list, new, get, update, delete, revoke)
- ✅ Phase 4: Client Access Commands (get, grant, revoke, update)
- ✅ Phase 5: Vault Commands (list, get, set, delete)
- ✅ Phase 6: Polish & Packaging
  - ✅ Error handling (per-command try/except with Rich-formatted errors)
  - ✅ Help text (Typer docstrings on all commands)
  - ✅ Packaging as installable CLI tool via Poetry scripts
  - ✅ Testing: unit, integration, and smoke suites, all passing; CI via `.github/workflows/test.yml`
- ✅ `client new` options for public clients (`is_public`, `redirect_uris`) — #8, PR #12
- ✅ `--dry-run` flag on all client and vault commands, showing the equivalent `campus_python` code — #5, PR #13

### In Progress / Pending
- ⏳ API Resource Commands (timetable, assignments, circles, users) — tracked in #4 (scope below)

---

## Project Structure
```
campus-cli/
├── main.py                 # Windows shim workaround for Poetry entry point (do not remove)
├── campus_cli/
│   ├── __init__.py
│   ├── api.py              # Campus API client wrapper
│   ├── cli.py              # Main CLI entry point
│   ├── config.py           # Configuration management
│   ├── credentials.py      # Credential storage abstraction
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── common.py       # Shared utilities (token refresh, API client, --dry-run option)
│   │   ├── login.py        # OAuth login flow (login, logout, refresh, status)
│   │   ├── client.py       # Client management commands
│   │   └── vault.py        # Vault commands
│   └── utils/
│       ├── __init__.py
│       └── output.py       # Formatted output (table/json, dry-run Python snippets)
├── tests/
├── docs/
├── .devcontainer/
├── scripts/                # Git hook installers (install-hooks.sh/.ps1)
├── pyproject.toml
└── README.md
```

## Technology Stack
- **Language**: Python 3.11 (pinned `>=3.11,<3.12`)
- **CLI Framework**: Typer (modern, type-annotated CLI built on Click)
- **Output Formatting**: Rich for beautiful terminal output
- **Credential Storage**: keyring library with platform backends
- **API Client**: campus-api-python (git dependency, `main` branch)

## Pending Features (Not Yet Implemented)

### API Resource Commands (#4)
The following resources are available in `campus-api-python` but not yet exposed in the CLI.
New commands should follow the existing conventions and ship with `--dry-run`
parity (shared `dry_run_option()` in `auth/common.py`, `print_python_api()` in
`utils/output.py`; API-resource snippets will need the `campus.api` bearer line
in the preamble).

#### Timetable Commands
- `campus timetable list` - List all timetables
- `campus timetable get-current` - Get current timetable ID
- `campus timetable set-current <id>` - Set current timetable
- `campus timetable get-next` - Get next timetable ID
- `campus timetable set-next <id>` - Set next timetable
- `campus timetable get <id>` - Get timetable metadata
- `campus timetable entries <id>` - List timetable entries

#### Assignment Commands
- `campus assignment list [--created-by <teacher>]` - List assignments
- `campus assignment new` - Create new assignment
- `campus assignment get <id>` - Get assignment details
- `campus assignment update <id>` - Update assignment
- `campus assignment delete <id>` - Delete assignment
- `campus assignment links add <id>` - Add classroom link

#### Circle Commands
- `campus circle list` - List circles
- `campus circle new` - Create new circle
- `campus circle get <id>` - Get circle details
- `campus circle update <id>` - Update circle
- `campus circle delete <id>` - Delete circle
- `campus circle members list <id>` - List circle members
- `campus circle members add <id> <member>` - Add member
- `campus circle members remove <id> <member>` - Remove member

#### User Commands
- `campus user list` - List users
- `campus user new` - Create new user
- `campus user get <id>` - Get user details
- `campus user activate <id>` - Activate user
- `campus user delete <id>` - Delete user

---

## API Integration Notes

### campus-api-python Usage
The CLI uses the `campus_python` package (from campus-api-python) which provides:

- `Campus` class - Unified client interface
- `auth.clients` - OAuth client management
- `auth.vaults` - Vault key-value storage
- `auth.users` - User management
- `api.timetables` - Timetable management
- `api.assignments` - Assignment management
- `api.circles` - Circle management

### Authentication Pattern
```python
from campus_cli.auth.common import get_api_client

# Get authenticated client (with auto-refresh)
api = get_api_client()

# Access resources
clients = api.auth_clients.list()
client = api.auth_clients[client_id].get()
vault_keys = api.auth_vaults[label].keys()
```

### Error Handling
- API errors from `campus_python.errors` are propagated
- KeyErrors indicate missing resources (vaults, keys)
- HTTP errors are raised via `raise_for_status()`

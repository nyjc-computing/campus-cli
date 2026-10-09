# campus-cli

Command-line interface for Campus API

## Installation

```bash
git clone https://github.com/nyjc-computing/campus-cli.git
cd campus-cli
pip install .
```

This installs the `campus` command system-wide.

## Usage

```bash
# Authenticate with Campus API
campus auth login

# Authenticate requesting a management scope (#865; requires the
# client's registered allowlist to include it — the server rejects
# unknown scopes)
campus auth login --scope clients:write

# Show what the stored token can do: client, endpoint, principal,
# scopes, expiry — plus a lightweight server-side validity check
# (network errors are reported without failing; exit code 0)
campus auth status

# Same, as JSON for scripts and agents
campus auth status --json

# Skip the validity check entirely (no network calls)
campus auth status --offline

# Create an OAuth client
campus client new --name "My App" --description "My application"

# Generate the client's secret (only time it is shown)
campus client revoke --client-id <id>

# Manage users (requires users:* scopes and users-admin designation)
campus user list
campus user new --email "new.member@school.edu" --name "New Member"
campus user activate --user-id "new.member@school.edu"

# List vault entries
campus vault list --vault myvault

# Preview any command as equivalent Python code (no API call made)
campus client new --name "My App" --description "My application" --dry-run
```

### Token scopes

`campus auth login --scope <scope>` (repeatable: `--scope read
--scope clients:write`) sets the scopes the new token will carry.
The semantics are exact-request, not Google-style accumulation:

- **The token carries exactly the requested scopes.** With no
  `--scope`, the server default for the CLI client (`read write`)
  applies — nothing is inferred from what your account is allowed
  to do.
- **Scopes never accumulate across logins.** The server holds a
  single live credential per `(user, client)`; a new login
  **replaces** it, and the previous token stops authenticating
  outright (supersession-is-deletion, campus invariant A5).
  Re-login with a wider scope is therefore the upgrade path — but
  it invalidates every process still holding the old token
  mid-flight.
- **There is no incremental-consent shortcut.** Needing a new
  scope always means a fresh device flow (browser round-trip);
  campus invariant A2 (no silent widening). `campus auth refresh`
  reissues exactly the granted scopes and never widens them.
- **Management scopes are monotonic**: `clients:admin` ⊇
  `clients:write` ⊇ `clients:read`, and `users:admin` ⊇
  `users:write` ⊇ `users:mod` ⊇ `users:read`, so request only the
  highest tier you need. The users tiers map to commands: read
  lists/gets, mod activates, write creates/renames, admin deletes.
- **The client allowlist is fail-closed.** A scope outside the
  CLI client's registered `allowed_scopes` fails the login
  outright with `invalid_scope`; an operator must widen the
  allowlist first (`campus client update --client-id <id>
  --allowed-scope <scope>`). Carrying a management scope is still
  not enough on its own — the authorizing account must also be a
  designated admin user server-side (campus invariant A8): clients
  scopes consult `AUTH_ADMIN_USER_IDS`, users scopes consult
  `AUTH_USERS_ADMIN_USER_IDS` (a clients-admin is not a
  users-admin).

**Check before you re-login:** `campus auth status` reports the
scopes the stored token carries (along with the client, endpoints,
principal and expiry), so scripts and agents can answer "what can
this token do?" before hitting a 403. Use `--json` for
machine-readable output; `--offline` skips the validity check when
no network is wanted. Scopes are recorded locally at login —
credentials stored before this was recorded show them as unknown
until the next login. `campus auth status` exits 1 when you are not
logged in or the server rejects the stored token, and 0 otherwise
(including when the server is unreachable, which is reported as a
warning).

For scripts and agents: request the full scope set you will need
up front, and treat a 403 `Token lacks '<scope>'` as the cue to
re-run login with that scope — expecting the old token to die when
you do.

Server-side references (campus `weekly` branch): the
[device flow](https://github.com/nyjc-computing/campus/blob/weekly/docs/auth-login-flow.md#device-flow-clis--how-it-differs)
section of the campus login-flow doc, and the campus
[token invariants](https://github.com/nyjc-computing/campus/blob/weekly/docs/auth-token-invariants.md)
(A2 no silent widening, A5 supersession-is-deletion, A8 management
scopes never self-confer).

### Dry-run mode

All `client`, `user` and `vault` commands accept `--dry-run`. Instead of
authenticating and calling the API, the command prints the equivalent
Python snippet using the
[campus-api-python](https://pypi.org/project/campus-api-python/)
library — useful for learning how to call the Campus API from Python:

```python
from campus_python import Campus

campus = Campus(timeout=30, mode="device")
campus.auth.client.set_bearer_authorization("<access_token>")

client = campus.auth.clients.new(
    name='My App',
    description='My application',
)
print(client.id)
```

### Non-interactive use (scripts, CI, agents)

Destructive commands — `auth logout`, `client delete`, `client revoke`,
`user delete`, `vault delete` — confirm before acting. When no terminal is attached
the CLI never blocks waiting for input: it refuses immediately with an
error naming the remedy. Waive the confirmation per command with
`--confirm`/`-y`, or for a whole session with the `CAMPUS_ASSUME_YES`
environment variable (`1`/`true`/`yes`):

```bash
campus client delete --client-id <id> -y    # per command
CAMPUS_ASSUME_YES=1 campus auth logout      # per session
```

Automation should expect exit code 1 and a `Refusing to proceed`
message on stderr when a destructive command is invoked without a
waiver.

## Development

For development and testing, use Poetry to install the project with development dependencies:

```bash
poetry install
poetry run pytest
```

Run the CLI using `poetry run`:

```bash
poetry run campus --help
```

If you use `poetry shell` to activate the virtual environment and encounter `ModuleNotFoundError: No module named 'main'`, exit the shell and rebuild:

```bash
exit
rm -f .venv/Scripts/campus.exe .venv/Scripts/campus
poetry build && poetry install
poetry shell
```

If you don't have Poetry installed:

```bash
pip install poetry
```

## Documentation

- [Development Guide](docs/development.md) - Testing, hooks, and development workflow
- [Product Requirements](docs/PRD.md) - Product requirements document
- [Implementation Plan](docs/plan.md) - Implementation details

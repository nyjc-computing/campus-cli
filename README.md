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

# Create an OAuth client
campus client new --name "My App" --description "My application"

# Generate the client's secret (only time it is shown)
campus client revoke --client-id <id>

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
  `clients:write` ⊇ `clients:read`, so request only the highest
  tier you need.
- **The client allowlist is fail-closed.** A scope outside the
  CLI client's registered `allowed_scopes` fails the login
  outright with `invalid_scope`; an operator must widen the
  allowlist first (`campus client update --client-id <id>
  --allowed-scope <scope>`). Carrying a management scope is still
  not enough on its own — the authorizing account must also be a
  designated admin user server-side (campus invariant A8).

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

All `client` and `vault` commands accept `--dry-run`. Instead of
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
`vault delete` — confirm before acting. When no terminal is attached
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

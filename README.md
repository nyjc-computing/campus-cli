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

# Manage users (needs a users:* grant row AND the matching scope)
campus user list
campus user new --email "new.member@school.edu" --name "New Member"
campus user activate --user-id "new.member@school.edu"

# See — and administer — who can do what (#883 grant store)
campus grant list
campus grant grant --grantee-type user --grantee-id someone@school.edu \
    --resource-type users --level write

# campus.audit: mint a student's trace-reading key (operator, #54)
CAMPUS_AUDIT_API_KEY=<operator key> campus audit login
campus audit keys new --name "Alice" --owner alice@school.edu \
    --scope traces:read --rate-limit 60
campus audit keys list --owner alice@school.edu

# …and the queries that key unlocks (from any machine the student logs in on)
campus audit traces list --limit 10
campus audit traces search --path /auth/v1/users/ --status 500
campus audit traces get --trace-id <32-char hex id>

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
- **Management authority = grant row AND scope.** Carrying a
  management scope is only half the story: the authorizing account
  must also hold a matching row in the access-grant store —
  `campus grant list` shows the matrix, `campus grant grant/revoke`
  administers it (operator or a same-vocabulary admin only; no
  principal administers its own grants, and vocabulary-level
  `clients:admin` rows are rejected). Clients grant rows cap at
  write: registering or deleting clients stays operator/root-only
  (campus invariant A8, nyjc-computing/campus#883).
- **The super-admin root is the one exception** (A8 carve-out): the
  env-nominated `AUTH_SUPER_ADMIN` account holds full authority with
  no grant rows and no scope requirement. Safeguard it; use it to
  seed grants, then work day-to-day on a sub-admin account.
- **The client allowlist is fail-closed.** A scope outside the
  CLI client's registered `allowed_scopes` fails the login
  outright with `invalid_scope`; an operator must widen the
  allowlist first (`campus client update --client-id <id>
  --allowed-scope <scope>`).

**Check before you re-login:** `campus auth status` reports the
scopes the stored token carries (along with the client, endpoints,
principal and expiry), so scripts and agents can answer "what can
this token do?" before hitting a 403. Use `--json` for
machine-readable output; `--offline` skips the validity check when
no network is wanted. It also shows your grant rows when your
account may read them (operator, root, or grants admin). Scopes are
recorded locally at login —
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

### campus.audit: API-key auth (#54)

The audit service (`/audit/v1`) is a separate, user-blind deployment
that does **not** accept OAuth tokens: it authenticates with its own
API keys (`audit_v1_…`) sent as Bearer credentials. `campus audit` is
the CLI's only command group using this second credential, stored in
the same credential store as your OAuth tokens and bound to the audit
URL it was stored for (per `ENV`/`CAMPUS_ENV` or `CAMPUS_AUDIT_URL`,
like every other endpoint):

```bash
# Store a key: the CAMPUS_AUDIT_API_KEY env var, an interactive prompt
# (hidden input), or --api-key. Prefer the first two: --api-key lands
# the key in your shell history and in the process list. The key is
# verified against the service first (--skip-verify stores it without
# the round trip)
CAMPUS_AUDIT_API_KEY=audit_v1_… campus audit login
campus audit login                 # prompts for the key
campus audit login --api-key audit_v1_…

# …and the login state is cleared locally by:
campus audit logout

# What does this install hold? A purely offline local view (no network
# call): whether a key is stored, the audit URL it is bound to, the URL
# the CLI currently targets (a mismatch is called out the way the
# commands' guard does), and when the key was stored. Exit 1 when no
# key is stored. --json emits the same fields for scripts.
campus audit status
```

`--json` in this group prints the server response verbatim, so every
command has one shape: list envelopes keep their `count`
(`keys list`) and pagination `cursor` (`traces list/search`); a
bodyless action such as `keys revoke` reports `{"id": …, "revoked":
true}`.

Two roles use the group:

- **The operator** holds the key with `apikeys:*` scopes (the one
  seeded from the server's `AUDIT_OPERATOR_API_KEY`) and administers
  everyone else's keys — mint, inspect, update, rotate, revoke:

  ```bash
  campus audit keys new --name "Alice" --owner alice@school.edu \
      --scope traces:read --rate-limit 60 --expires-at 2026-12-31T23:59:59Z
  campus audit keys list --owner alice@school.edu
  campus audit keys get --key-id <id>
  campus audit keys update --key-id <id> --scope traces:read --rate-limit 120
  campus audit keys regenerate --key-id <id>   # rotation; old value dies
  campus audit keys revoke --key-id <id>       # record kept for audit
  ```

  Plaintext key material is shown exactly once, at creation and at
  regeneration (the server keeps only the hash) — pass it to the
  student, who stores it with `campus audit login`. `owner_id` is a
  free-form label used for organization and filtering only (an email
  is the convention, but the server accepts any string);
  campus.audit is user-blind and self-contained by design, so it
  never resolves to a campus user account.

- **Students** log in with their minted key and query traces
  (gated on `traces:read`):

  ```bash
  campus audit traces list --limit 10            # recent, newest first
  campus audit traces search --path /auth/v1/users/ --status 500
  campus audit traces search --user alice@school.edu --since 2026-10-20T00:00:00Z
  campus audit traces get --trace-id <32-char hex>
  ```

  List and search paginate: when a page has more, the command prints
  the `--cursor` token to continue with. `logout` only clears the
  local copy of a key — a leaked key is disabled with
  `campus audit keys revoke` (operator) or by letting `--expires-at`
  pass.

### Dry-run mode

All `client`, `user`, `vault` and `audit` commands accept `--dry-run`.
Instead of authenticating and calling the API, the command prints the
equivalent Python snippet using the
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

`campus audit` snippets open with the audit client instead — the
service takes its own API key, not an OAuth token:

```python
from campus_python import AuditRoot, CampusRequest

campus_audit = AuditRoot(json_client=CampusRequest(
    base_url="<audit_url>", timeout=30, mode="device",
))
campus_audit.client.set_bearer_authorization("<audit_api_key>")
```

### Non-interactive use (scripts, CI, agents)

Destructive commands — `auth logout`, `client delete`, `client revoke`,
`user delete`, `vault delete`, `audit logout`, `audit keys revoke`,
`audit keys regenerate` — confirm before acting. When no terminal is attached
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

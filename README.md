# campus-cli

Command-line interface for Campus API

User-facing documentation lives at
<https://nyjc-computing.github.io/campus-cli/> (guides + a command
reference generated from the app definition — see AGENTS.md for the
docs workflow and the version-bump docs rule).

## Installation

Install a versioned release with [pipx](https://pipx.pypa.io) (recommended —
isolated venv, the `campus` command on your PATH):

```bash
pipx install https://github.com/nyjc-computing/campus-cli/releases/download/v0.10.7/campus_cli-0.10.7-py3-none-any.whl
```

or with pip into your Python environment:

```bash
pip install https://github.com/nyjc-computing/campus-cli/releases/download/v0.10.7/campus_cli-0.10.7-py3-none-any.whl
```

Releases are tagged `vX.Y.Z`; swap the URL for the version you want. Every
release wheel carries the pinned `campus-api-python` release it was tested
against — pip resolves it from GitHub Releases automatically, so no git and
no source checkout are needed.

### Development

```bash
git clone https://github.com/nyjc-computing/campus-cli.git
cd campus-cli
poetry install
poetry run campus version
```

## Usage

```bash
# Authenticate with Campus API
campus auth login

# Authenticate requesting a management scope (#865; requires the
# client's registered allowlist to include it — the server rejects
# unknown scopes)
campus auth login --scope clients:write

# Hold several logins at once — named sessions (#113): one session is
# one account on one environment. Every command uses the ACTIVE one.
campus auth login --as dev-alice     # store as a named session + activate it
campus auth use                      # list sessions (active one marked)
campus auth use prod-admin           # switch the active session
campus auth status --all             # inventory every stored session
campus auth logout --as dev-alice    # remove one slot; --all clears every slot

# Headless/agent login: print the verification link instead of opening
# a browser here; approve from any machine's browser (consent page shows
# client + scopes; the code expires in ~10-15 minutes)
campus auth login --as agent --no-browser

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

# User directory (campus.api facade, campus#1226 - staff read via the
# staff:viewer baseline; no grant row)
campus user list                # or: --q "substring"
campus user get --user-id "someone@school.edu"

# Manage users (campus.auth management surface - needs a users:* grant
# row AND the matching scope; campus#883/#887)
campus auth user new --email "new.member@school.edu" --name "New Member"
campus auth user activate --user-id "new.member@school.edu"

# Campus API resources — reads (campus-cli#4 Phase A)
campus assignment list --created-by "teacher@school.edu"
campus assignment get --assignment-id <id>
campus submission list          # or: by-assignment --assignment-id <id>
campus submission by-student --student-id "student@school.edu"
campus submission get --submission-id <id>
campus timetable list           # or: current / next
campus timetable entries --timetable-id <id>
campus circle list
campus circle members list --circle-id <id>
campus circle members check --circle-id timetable.admin --member-id "t@school.edu"
campus circle roles --user-id "teacher@school.edu"
campus circle members check --circle-id timetable.admin --member-id "t@school.edu"
campus circle roles --user-id "teacher@school.edu"

# Campus API resources — writes (campus-cli#4 Phase B)
campus assignment new --title "Quiz 1" --description "..."
campus assignment update --assignment-id <id> --title "Renamed"
campus assignment delete --assignment-id <id>            # -y skips the prompt
campus assignment links add --assignment-id <id> \
    --course-id <classroom-course> --coursework-id <classroom-coursework>
campus circle new --name "13A2" --tag class
campus circle members add --circle-id <id> --member-id <user> --access 3
campus circle members set --circle-id <id> --member-id <user> --access 5
campus circle members remove --circle-id <id> --member-id <user>
# pointer setters retired (campus#1222): current/next derive from validity windows
campus timetable metadata update --timetable-id <id> \
    --start-date 2027-01-01 --end-date 2027-06-01
campus submission submit --submission-id <id>
campus submission unsubmit --submission-id <id>          # gated on campus#1071
campus submission new --assignment-id <id> --student-id <user> \
    --course-id <classroom-course>
campus submission responses add --submission-id <id> \
    --question-id q1 --response-text "42"
campus submission feedback add --submission-id <id> \
    --question-id q1 --feedback-text "Well done"
campus timetable new --metadata '{"start_date": "2027-01-01", \
    "end_date": "2027-06-01", "filename": "2027.json"}' \
    --data-file lessongroups.json                        # data needs a
                                                         # 'lessongroups' key
campus file put --slug my-notes --file notes.txt --content-type text/plain
campus file get-content --slug my-notes --output notes.txt
campus app put --slug my-app --file app.html             # publishes HTML app
campus app get-content --slug my-app

# See — and administer — who can do what (#883 grant store)
campus grant list
campus grant grant --grantee-type user --grantee-id someone@school.edu \
    --resource-type users --level write

# campus.audit: mint a student's trace-reading key (operator, #54)
CAMPUS_AUDIT_API_KEY=<operator key> campus audit login
campus audit keys new --name "Alice" --owner alice@school.edu \
    --role traces-viewer --rate-limit 60
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

### Machine-readable output

`--json` always emits raw, spec-valid JSON: string values are
byte-exact and never soft-wrapped to the terminal width (#69). On an
interactive terminal the same output is syntax-highlighted for
reading — its line wrapping is display-only, so pipe through `cat`
or `jq` (or redirect to a file) for the raw form. Agent tools that
allocate a pty can force the raw form with `CAMPUS_CLI_AGENT=1`.

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

### Environment routing

The CLI targets **production** by default (gateway
`https://nyjc-campus.up.railway.app`); it talks to one auth deployment and
one API deployment at a time. Set `ENV=development` (or
`CAMPUS_ENV=development`; ENV wins, `testing` aliases development) to fall
back to the dev gateway (`https://campus-development.up.railway.app`).
The `staging` environment is retired; selecting it raises an error.

Each service URL resolves independently, following the campus-common
`resolve_base_url` contract:

1. `CAMPUS_<SERVICE>_URL` (e.g. `CAMPUS_AUTH_URL`) — primary override. The
   CLI's auth layer expects this to carry the `/auth/v1` suffix; the api
   and audit clients take bare origins (they append `/api/v1`, `/audit/v1`
   themselves).
2. `<SERVICE>_URL` — bare alias (`AUTH_URL`, `API_URL`, `AUDIT_URL`).
3. The config file's `auth_url` / `audit_url` keys (CLI-local tier).
4. `CAMPUS_BASE_URL`, then `BASE_URL` — one gateway origin standing in for
   any missing service URL; the CLI appends the `/auth/v1` prefix for
   auth, and the api/audit clients route through the gateway unchanged.
5. The deployment's built-in gateway default.

- **prod (default)**: `https://nyjc-campus.up.railway.app/auth/v1` + `https://campusapi.up.railway.app`
- **dev**: `https://campus-development.up.railway.app/auth/v1` + `https://campusapi-development.up.railway.app`

Override and base values must be bare origins (`scheme://host[:port]`, no
path or trailing slash); a malformed value raises `ValueError` naming the
variable. For one-off calls against another deployment, prefix the env vars:

```bash
CAMPUS_AUTH_URL=https://nyjc-campus.up.railway.app/auth/v1 CAMPUS_API_URL=https://campusapi.up.railway.app campus circle list
```

**Named sessions, one active.** The OS keyring holds each login in its
own slot (#113): one session is one account on one environment, and the
config file's active-session pointer decides which one every command
uses (`campus auth use` to switch, `campus auth status --all` to
inventory). Each slot still records the auth endpoint that minted it,
and the endpoint-mismatch check applies per session. The supersession
rule still applies inside one (account, environment) pair — the server
keeps a single live credential per user and client, so re-logging the
same account on the same environment invalidates that account's older
slots. See [Named login sessions](docs/authentication.md#named-login-sessions).
Pre-0.10.4 installs upgrade in place: their existing credentials become
the default slot.

**Polling note (campus-cli ≥0.7.3):** production strips
`details.oauth_error` from token-error envelopes — the RFC 8628 error
code device-flow polling keys on — as part of its production detail
strip. CLI 0.7.3+ recovers the code from the campus error code
(`AUTH_AUTHORIZATION_PENDING` → `authorization_pending`) and keeps
polling; older CLIs abort the flow after a single "Authorization
pending".

### Clients never speak browser namespaces

The campus gateway serves consumer apps under browser namespaces
(`/timetable/`, `/apps/`, `/admin/`, `/profile/`, `/classroom/`) — a
browser-surface construct only, and invisible to this CLI. The CLI, the
`campus_python` SDK, and any machine-to-machine caller address services
directly by configured origin (see
[Environment routing](#environment-routing)) plus the services'
unprefixed paths: `/auth/v1/…`, `/api/v1/…`, `/audit/v1/…`.
`X-Forwarded-Prefix`, `SCRIPT_NAME`, and `PUBLIC_URL` only shape
generated browser-facing URLs; they never appear in CLI configuration
or CLI traffic. Normative spec:
[url-namespacing.md](https://github.com/nyjc-computing/campus/blob/weekly/docs/url-namespacing.md)
(umbrella issue: campus#1295).

### campus.audit: API-key auth (#54)

The audit service is a separate, user-blind deployment with two auth
lanes. Its versioned API (`/audit/v1`) — everything `campus audit`
talks to — accepts only the service's own API keys (`audit_v1_…`) sent
as Bearer credentials, never OAuth tokens or campus accounts. The
service's web UI has its own, separate gate: campus accounts on the
server's `AUDIT_ADMINS` list sign in as **superadmins** (they may view
traces *and* manage keys in the browser), and in development
environments an audit API key can sign in too. None of that issues CLI
credentials: `campus audit` is the CLI's only command group using a
second credential, stored in the same credential store as your OAuth
tokens and bound to the audit URL it was stored for (per
`ENV`/`CAMPUS_ENV` or `CAMPUS_AUDIT_URL`, like every other endpoint):

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

The service gates everything through two capabilities, and a key earns
them scope by scope: `traces:read` for trace surfaces (the CLI's
`traces` commands, and the browser trace viewer via key sign-in),
`apikeys:write` for key management. A key with `apikeys:write` gains
no trace access, and a key with `traces:read` gains no key
management; `apikeys:read` alone is an API/CLI privilege that does not
admit a browser session. Web superadmins hold both capabilities by
being on the list.

Two roles use the group:

- **The operator** holds a key carrying `apikeys:read`/`apikeys:write`
  — the deployment seeds one from the server's `AUDIT_OPERATOR_API_KEY`
  env var (with every `traces:*` scope besides) — and administers
  everyone else's keys — mint, inspect, update, rotate, revoke:

  ```bash
  campus audit keys new --name "Alice" --owner alice@school.edu \
      --role traces-viewer --rate-limit 60 --expires-at 2026-12-31T23:59:59Z
  campus audit keys list --owner alice@school.edu
  campus audit keys get --key-id <id>
  campus audit keys update --key-id <id> --role traces-viewer --rate-limit 120
  campus audit keys regenerate --key-id <id>   # rotation; old value dies
  campus audit keys revoke --key-id <id>       # record kept for audit
  ```

  **Roles vs scopes.** `--role` names one of the service's roles — a
  bundle of scopes it owns (`traces-viewer`, `traces-searcher`,
  `traces-producer`, `key-operator`), so the holder gets a reviewed
  privilege set instead of a hand-assembled one. `--scope` is for
  anything the roles do not cover. The two are mutually exclusive, and
  the service owns the catalogue: an unknown role is refused with the
  names of the roles it does have.

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

  In a development environment the same `traces:read` key also signs
  into the audit web UI's trace viewer, where the session holds
  exactly the key's scopes; revoking or re-scoping the key ends the
  browser session on its next request. That sign-in path does not
  exist outside development.

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

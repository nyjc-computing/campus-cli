# Authentication & scopes

## Logging in

```bash
campus auth login                 # server default scopes (read write)
campus auth login --scope clients:write
campus auth login --scope read --scope clients:write   # repeatable
```

`campus auth login` runs the OAuth device flow: a browser opens with a
pre-filled code, and the minted token lands in your system keyring
(through the SDK's session store). Public clients need no secrets on
your machine.

On a headless box — or when an agent runs the login and you authorize
from your own session — add `--no-browser`: the verification link is
printed instead of a browser being opened here, and you click it from
any machine to approve the pending request.

`campus auth status` reports the stored token's client, endpoints,
principal, scopes, and expiry, plus a lightweight server-side validity
check (network errors are reported without failing; exit code stays
0). Use `--json` for scripts, `--offline` to skip the check. It exits 1
only when you are not logged in or the server rejects the token. When
your account may read grant rows (operator, root, or grants admin) it
also shows them.

## Named login sessions

One session is one account on one environment (auth endpoint). Named
sessions (#113) let one machine hold several at once — e.g. a
development student account, a production operator account, and an
agent's everyday token — without re-running the device flow at every
switch:

```bash
campus auth login --as dev-alice      # store as a named session + activate it
campus auth use                       # list sessions (active one marked)
campus auth use prod-admin            # switch the active session
campus auth use --default             # back to the unnamed default slot
campus auth status                    # describes the ACTIVE session
campus auth status --all              # inventory every stored session
campus auth logout --as dev-alice     # revoke + remove one named session
campus auth logout --all              # revoke + clear every session
```

### How it works

Every command reads whichever session is **active** — the config
file's `active_session` pointer. Without one, that is the unnamed
default slot: installs upgrading from before #113 keep working
unchanged, and their existing credentials simply become the default
slot. Tokens expire and refresh per session as usual, the
endpoint-mismatch check applies per session, plain `campus auth login`
overwrites the ACTIVE session's credentials, and plain `campus auth
logout` logs the active session out (run `campus auth use` first if
you are not where you think you are).

Credentials live in the OS keyring, namespaced per slot
(`session/<name>/access_token`, ...), so each slot is one entry per
field in Windows Credential Manager / your desktop's equivalent. The
campus.audit API key (`campus audit login`) is a **global per-install
credential**: no session logout touches it.

Session names are 1–64 characters of letters, digits, dots, dashes and
underscores (starting with a letter or digit) — safe both as keyring
account names and as path segments.

### The one caveat: supersession

The server keeps **one live credential per (user, client)**, and a new
login for the same pair deletes the old token outright (campus
invariant A5). Named sessions therefore give true isolation only when
they differ in **account or environment**:

- `--as dev` on the development gateway and `--as prod` on production:
  fully independent.
- Two sessions logged into the *same* account on the *same*
  environment: the newer login invalidates the older slot's token
  server-side — `campus auth status` in that older slot then reports
  the token as rejected.

So give agents their own named session and never re-login the human's
account from one; and when a slot reports invalid right after another
login, that is supersession, not a bug — log in again for that slot or
drop it with `campus auth logout --as <name>`.

### Agent-mediated login (headless machines)

On a headless box — or whenever an agent runs the login — combine a
named session with `--no-browser`:

```bash
campus auth login --as agent --no-browser
```

The CLI prints the verification link (the user code is pre-embedded,
RFC 8628 §3.3.1) and polls; no browser is opened on the machine
running the command. Open the link in **any** browser — a remote
shell, another desktop, a phone — review the consent page (it names
the client and the requested scopes), and approve: the polling command
completes and stores the token. The code expires in ~10–15 minutes, so
click it promptly. An explicit `--scope` set rides along as usual.

This is the safe default for agents: the human's click is the consent
act, the agent never disturbs the human's active session, and no
localhost redirect is involved, so "remote" costs nothing extra.

### Troubleshooting

- `campus auth use ghost` fails with "No stored session" — log in
  first: `campus auth login --as ghost`.
- A slot shows `EXPIRED` in `campus auth status --all` — activate it
  (`campus auth use <name>`) and run `campus auth refresh`; a stored
  refresh token reissues the same scopes.
- A slot reports the server-side check as `invalid` right after
  another login for the same account/environment — supersession (see
  above), not a bug.

## How scopes work

`--scope <scope>` sets the scopes the new token will carry. The
semantics are exact-request, not Google-style accumulation:

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
- **There is no incremental-consent shortcut.** Needing a new scope
  always means a fresh device flow (browser round-trip);
  campus invariant A2 (no silent widening). `campus auth refresh`
  reissues exactly the granted scopes and never widens them.
- **Management scopes are monotonic**: `clients:admin` ⊇
  `clients:write` ⊇ `clients:read`, and `users:admin` ⊇
  `users:write` ⊇ `users:mod` ⊇ `users:read`, so request only the
  highest tier you need. The users tiers map to commands: read
  lists/gets, mod activates, write creates/renames, admin deletes.

## Who may do what: grant rows AND scope

**Management authority = grant row AND scope.** Carrying a management
scope is only half the story: the authorizing account must also hold a
matching row in the access-grant store (#883). `campus grant list`
shows the matrix; `campus grant grant/revoke` administers it (operator
or a same-vocabulary admin only; no principal administers its own
grants, and vocabulary-level `clients:admin` rows are rejected).
Clients grant rows cap at `write`: registering or deleting clients
stays operator/root-only (campus invariant A8).

**The super-admin root is the one exception** (A8 carve-out): the
env-nominated `AUTH_SUPER_ADMIN` account holds full authority with no
grant rows and no scope requirement. Safeguard it; use it to seed
grants, then work day-to-day on a sub-admin account.

**The client allowlist is fail-closed.** A scope outside the CLI
client's registered `allowed_scopes` fails the login outright with
`invalid_scope`; an operator must widen the allowlist first:

```bash
campus client update --client-id <id> --allowed-scope <scope>
```

**Check before you re-login:** `campus auth status` reports the scopes
the stored token carries, so scripts and agents can answer "what can
this token do?" before hitting a 403. Scopes are recorded locally at
login — credentials stored before this was recorded show them as
unknown until the next login.

## Audit API keys (operators)

Audit trace access is separate from login scopes: mint a
trace-reader key with an operator key, then log in with it:

```bash
CAMPUS_AUDIT_API_KEY=<operator key> campus audit login
campus audit keys new --name "Alice" --owner alice@school.edu \
    --role traces-viewer --rate-limit 60
campus audit traces list --limit 10
```

See the [command reference](reference/commands.md#campus-audit) for
the full audit surface.

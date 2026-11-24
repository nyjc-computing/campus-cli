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

## Named sessions

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
campus auth status --all              # inventory every stored session
campus auth logout --as dev-alice     # revoke + remove one named session
campus auth logout --all              # revoke + clear every session
```

Every command reads whichever session is active; tokens expire and
refresh per session as usual, and the endpoint-mismatch check applies
per session. Plain `campus auth login` overwrites the ACTIVE session's
credentials, and `campus auth logout` logs out the active session.
The campus.audit API key (`campus audit login`) is a global per-install
credential: no session logout touches it.

**Supersession still applies within one (account, environment)**: the
server keeps a single live credential per user and client, so a fresh
login for the same account on the same endpoint invalidates that
account's older token — including the copy stored in another session
slot. Named sessions are fully independent only when they differ in
account or environment; agents should use their own named session (or
`--no-browser`) rather than re-logging the human's account.

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

---
name: campus
description: >-
  Drive the Campus platform through the installed `campus` CLI: named
  login sessions (one account x one environment each), device-flow and
  remote --no-browser login, token status, OAuth client administration,
  user management, the #883 access-grant store, vault settings, and
  campus.audit (API key minting + trace queries). Use whenever the user
  mentions Campus, campus users/clients/grants/vaults/audit traces,
  wants to mint a student audit key, check who can administer what, or
  investigate an HTTP trace — and whenever a campus command returns
  401/403, to check login state first. OAuth sessions, upstream
  credentials, connections and brokered tokens are deliberately NOT
  exposed by the CLI; those are SDK-only.
---

# campus — the Campus platform CLI

## What you are driving

`campus` (campus-cli) is installed on this machine and on PATH; check
with `campus version` (prints `campus-cli version X.Y.Z`; named
sessions need ≥0.10.4). It installs from versioned release wheels;
source and docs live in `D:\nyjc-computing\campus-cli` (`README.md`,
docs site https://nyjc-computing.github.io/campus-cli/). Advanced
programmatic use goes through the `campus_python` SDK
(`D:\nyjc-computing\campus-api-python`), not the CLI.

## Auth: think in sessions

**One session = one account on one environment** (cli#113, ≥0.10.4).
Every command reads whichever session is ACTIVE — the config file's
`active_session` pointer (no pointer = the unnamed default slot; a
pre-0.10.4 install's existing credentials become that default slot).

```bash
campus auth login --as dev-alice    # device flow into a named session, then activate it
campus auth use                     # list sessions (active one marked)
campus auth use prod-admin          # switch the active session
campus auth status --all            # inventory every slot: principal, issuer, scopes, expiry
campus auth logout --as dev-alice   # revoke + remove one slot (-y; --all clears everything)
```

Plain commands all follow the active session: `campus auth login`
OVERWRITES it, `logout` logs it out, `refresh` rotates its token,
`status` describes it:

```bash
campus auth status            # + server-side validity check (exit 1 only if rejected/not logged in)
campus auth status --json     # raw JSON for scripts (adds "session": active slot or null)
campus auth status --offline  # skip the network validity check
campus auth refresh           # rotate the access token from the stored refresh token
```

Rules agents must know:

- **Take your own named session** (`campus auth login --as <agent>`);
  never re-login the human's active account — supersession (below)
  kills their live token mid-flight.
- **Supersession**: the server keeps ONE live credential per
  (user, client); a fresh login for the same account on the same
  environment invalidates that account's older slots. Sessions are
  truly independent only across different accounts OR environments.
- **Remote/headless login**: `campus auth login --as <name>
  --no-browser` prints the verification link (user code pre-embedded)
  and polls without opening a browser on this machine. Relay the link
  to the human; they click it from any machine and approve the consent
  page (client + requested scopes shown). Codes expire in ~10–15
  minutes — relay promptly, then WAIT for the login to finish; don't
  spin (login exits 0 on success, 1 on failure/denial/timeout).
- Credentials live in the OS keyring (Windows Credential Manager on
  this box), namespaced per slot. The campus.audit API key is GLOBAL —
  no session logout touches it.
- Non-TTY runs fail fast on prompts: pass `-y/--confirm` or set
  `CAMPUS_ASSUME_YES=1` on destructive commands (`logout` included).
- Upgrades: pipx refuses wheel-path upgrades — use
  `pipx install --force <release wheel URL>` from campus-cli's GitHub
  releases.

## Command map

| Group | Commands | Notes |
|-------|----------|-------|
| `campus auth` | `login` (`--as`, `--no-browser`, `--scope`), `logout` (`--as`/`--all`), `use`, `refresh`, `status` (`--all`/`--json`/`--offline`), `user` | named sessions (≥0.10.4); scopes are exact-request at login; `auth user` = management through campus.auth (list/get/new/activate/edit/delete; needs `users:*` grants + matching scope) |
| `campus client` | `list`, `new`, `get`, `update`, `delete`, `revoke` | OAuth client registration (operator authority) |
| `campus client access` | `get`, `grant`, `revoke`, `update` | a client's vault access records |
| `campus user` | `list` (`--q`), `get` | read-only directory facade through campus.api (campus#1226): staff read the full base via the staff:viewer baseline — no grant row; other callers get their circle-visible slice. Mutations are `campus auth user` |
| `campus grant` | `list`, `check`, `grant`, `revoke`, `delete` | the #883 "who can administer what" store |
| `campus vault` | `list`, `get`, `set`, `delete` | key/value settings inside a vault label |
| `campus audit` | `login`, `logout`, `status` | API-key auth (`--api-key` or `CAMPUS_AUDIT_API_KEY`); global credential, survives session logouts |
| `campus audit keys` | `list`, `new`, `get`, `update`, `revoke`, `regenerate` | mint student trace keys: `--role` or `--scope`, never both |
| `campus audit traces` | `list`, `get`, `search` | `search` filters: `--path --status --user --client --api-key-id --journey --since --until` |
| `campus assignment` | `list [--created-by]`, `get --assignment-id` | campus.api; writes: `new --title`, `update`, `delete`, `links add` |
| `campus submission` | `list [--assignment-id/--student-id/--course-id]`, `by-assignment`, `by-student`, `get --submission-id` | campus.api; writes: `new`, `update --submitted-at`, `submit`, `unsubmit` (gated on campus#1071), `responses add`, `feedback add` |
| `campus timetable` | `list`, `current`, `next`, `get --timetable-id`, `entries --timetable-id` | campus.api; writes: `new --metadata --data-file` (data key is `lessongroups`) + `metadata update` (pointer setters retired — campus#1222 derives current/next from validity windows) |
| `campus circle` | `list`, `get --circle-id`, `members list --circle-id` | campus.api; writes: `new --name --tag`, `update`, `delete`, `members add/set/remove` |
| `campus venue` | `list`, `get`, `create`, `update`, `delete` | campus.api; writes gated on venues.admin; `update` patches given fields, absent stay; `metadata` is whole-dict replace, `notes: null` clears |
| `campus file` | `list [--prefix]`, `get-meta --slug`, `get-content --slug [--output]`, `put --slug --file [--content-type] [--name]`, `delete` | content-addressed by-slug storage; slug is the stable address |
| `campus app` | same shape as `file` | publishes single-file HTML apps; defaults to text/html |

Grant semantics (#883): there is no `grant update` — `grant grant` raises
(vault bits OR in, management levels only go up), `grant revoke` lowers
(clears bits / covered levels, deletes the row at zero), `grant delete`
removes the row outright. Downgrading a level = revoke then grant.

## Conventions

- **`--json` is the machine-readable form on every read** — raw, spec-valid
  JSON, never soft-wrapped. Agents in a pty can force it with
  `CAMPUS_CLI_AGENT=1`. Parse stdout; don't screen-scrape.
- **`--dry-run` on every mutating command** prints the equivalent Python
  SDK snippet instead of calling the API — use it to show intent before
  acting.
- Destructive commands (delete/revoke/logout) confirm interactively; in
  scripts pass `-y`/`--confirm` or `CAMPUS_ASSUME_YES=1`.
- **Environment routing**: production is the default target (gateway
  `https://nyjc-campus.up.railway.app` + api
  `https://campusapi.up.railway.app`) — REAL DATA, default to read-only
  there unless the task says otherwise. `ENV=development` (or
  `CAMPUS_ENV=development`; ENV wins, `testing` aliases development)
  targets the dev fleet. Per-service resolution: `CAMPUS_<SERVICE>_URL`
  > `<SERVICE>_URL` > config file (`auth_url`/`audit_url`) >
  `CAMPUS_BASE_URL`/`BASE_URL` (a gateway origin standing in for any
  missing service URL; auth gets the `/auth/v1` suffix appended) >
  per-deployment default. Override per-call with `CAMPUS_AUTH_URL`
  (must include the `/auth/v1` suffix) and `CAMPUS_API_URL`. Staging is
  retired. A named session binds to the environment that minted it —
  keep one session per environment instead of re-login shuffling.
- **Some campus.api surfaces have no CLI group** — `subjcombi` (and
  parts of `bookings`) are API-only: drive them via the SDK, direct
  HTTP with the stored bearer, or ttv2's seed scripts
  (`scripts/seed_subjcombi.py` in
  `D:\nyjc-computing\nyxchange-timetable-v2`). Surfaces: subjcombi is
  `PUT /api/v1/subjcombi/{user_id}` (append-only, label-keyed, gated on
  the subjcombi.admin circle).

## Non-goals (design principle)

The CLI is a tool for users and agents; auth stays opaque. It will never
expose OAuth session, credential, or connections info, or fetch brokered
tokens — don't look for commands that do, and don't try to reconstruct
them over HTTP. ("Named sessions" are local credential slots, not the
server-side login sessions.) Advanced usage imports the SDK directly.
Issue #4 (campus.api resources) is COMPLETE as of 2026-11-06 — Phases
A/B/C all shipped; there are no deliberately-absent campus.api commands
left, only `campus submission unsubmit` awaiting the campus#1071 server
fix.

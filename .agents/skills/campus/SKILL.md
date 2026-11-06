---
name: campus
description: >-
  Drive the Campus platform through the installed `campus` CLI: device-flow
  login and token status, OAuth client administration, user management, the
  #883 access-grant store, vault settings, and campus.audit (API key minting
  + trace queries). Use whenever the user mentions Campus, campus
  users/clients/grants/vaults/audit traces, wants to mint a student audit
  key, check who can administer what, or investigate an HTTP trace — and
  whenever a campus command returns 401/403, to check login state first.
  Sessions, upstream credentials, connections and brokered tokens are
  deliberately NOT exposed by the CLI; those are SDK-only.
---

# campus — the Campus platform CLI

## What you are driving

`campus` (campus-cli) is installed on this machine and on PATH; check with
`campus version` (prints `campus-cli version X.Y.Z`). It installs from
versioned release wheels; source and docs live in
`D:\nyjc-computing\campus-cli` (`README.md`). Advanced programmatic use
goes through the `campus_python` SDK (`D:\nyjc-computing\campus-api-python`),
not the CLI.

## Auth

```bash
campus auth login            # device flow: prints a code + URL, waits for approval
campus auth status           # client, endpoint, principal, scopes, expiry + server-side validity check
campus auth status --json    # same, raw JSON for scripts/agents
campus auth status --offline # skip the network validity check
campus auth refresh          # rotate the access token from the stored refresh token
campus auth logout           # revoke server-side; prompts (use -y to confirm)
```

The token pair lives in the OS keyring. Non-TTY runs fail fast on prompts;
set `CAMPUS_ASSUME_YES=1` (or pass `-y/--confirm` on destructive commands)
for unattended use.

## Command map

| Group | Commands | Notes |
|-------|----------|-------|
| `campus auth` | `login`, `logout`, `refresh`, `status` | device flow; scopes requested at login (`--scope`) |
| `campus client` | `list`, `new`, `get`, `update`, `delete`, `revoke` | OAuth client registration (operator authority) |
| `campus client access` | `get`, `grant`, `revoke`, `update` | a client's vault access records |
| `campus user` | `list`, `new`, `get`, `activate`, `edit`, `delete` | needs `users:*` grants + matching scope |
| `campus grant` | `list`, `check`, `grant`, `revoke`, `delete` | the #883 "who can administer what" store |
| `campus vault` | `list`, `get`, `set`, `delete` | key/value settings inside a vault label |
| `campus audit` | `login`, `logout`, `status` | API-key auth (`--api-key` or `CAMPUS_AUDIT_API_KEY`) |
| `campus audit keys` | `list`, `new`, `get`, `update`, `revoke`, `regenerate` | mint student trace keys: `--role` or `--scope`, never both |
| `campus audit traces` | `list`, `get`, `search` | `search` filters: `--path --status --user --client --api-key-id --journey --since --until` |
| `campus assignment` | `list [--created-by]`, `get --assignment-id` | campus.api reads (#4 Phase A) |
| `campus submission` | `list [--assignment-id/--student-id/--course-id]`, `by-assignment`, `by-student`, `get --submission-id` | campus.api reads |
| `campus timetable` | `list`, `current`, `next`, `get --timetable-id`, `entries --timetable-id` | campus.api reads |
| `campus circle` | `list`, `get --circle-id`, `members list --circle-id` | campus.api reads |

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
- Destructive commands (delete/revoke) confirm interactively; in scripts
  pass `-y`/`--confirm` or `CAMPUS_ASSUME_YES=1`.
- **Environment routing**: the dev deployment is the default target.
  Override per-call with `CAMPUS_AUTH_URL` (must include the `/auth/v1`
  suffix) and `CAMPUS_API_URL`; `ENV`/`CAMPUS_ENV` also steer both CLI auth
  and the SDK. There is no staging/prod auth deployment yet.

## Non-goals (design principle)

The CLI is a tool for users and agents; auth stays opaque. It will never
expose session, credential, or connections info, or fetch brokered tokens —
don't look for commands that do, and don't try to reconstruct them over
HTTP. Advanced usage imports the SDK directly. campus.api resource WRITES
(assignment/submission/circle/timetable new, update, delete, submit;
timetable set-current/set-next; files and hosted-app publishing) are
tracked in campus-cli#4 Phase B and intentionally have no commands yet —
reads for assignment/submission/timetable/circle shipped in Phase A; don't
invent flags for the write half.

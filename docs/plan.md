# Implementation Plan

## Project Status

**Last Updated:** 2026-11-06

### Completed
- ✅ Phase 1: Core Infrastructure (CLI entry point, credentials, config, output formatting)
- ✅ Phase 2: Authentication (OAuth device flow via public `guest` client, logout with server-side revocation, token storage with endpoint binding, auto-refresh)
- ✅ Phase 3: OAuth Client Commands (list, new, get, update, delete, revoke)
- ✅ Phase 4: Client Access Commands (get, grant, revoke, update)
- ✅ Phase 5: Vault Commands (list, get, set, delete, labels — campus#1055 admin view)
- ✅ Phase 6: Polish & Packaging
  - ✅ Error handling, help text, non-interactive confirmations (`-y` / `CAMPUS_ASSUME_YES`, #27/#28)
  - ✅ `--dry-run` parity across all API-backed commands (equivalent `campus_python` snippets)
  - ✅ Versioned releases: tag-triggered wheel publishing + pipx/pip install from release URLs (#76); PyPI ruled out (direct-URL deps)
- ✅ User Commands (list, new, get, activate, edit, delete)
- ✅ Access-Grant Store Commands (#883: list, check, grant, revoke, delete)
- ✅ campus.audit Commands (#54: login/logout/status, keys lifecycle, trace queries)
- ✅ campus.api Resource Commands (#4, all three phases; live-verified against dev):
  - ✅ Phase A reads: assignment/submission/timetable/circle (PR #80, v0.3.0)
  - ✅ Phase B writes: assignment/circle/timetable/submissions + `campus file` / `campus app` by-slug groups (PR #81, v0.4.0)
  - ✅ Phase C structured payloads: timetable new, submission new, responses/feedback add (v0.5.0)
  - ⏳ `campus submission unsubmit` shipped but gated on the campus#1071 server fix (null-only PATCH body rejected as "Empty request body")
- ✅ Agent skill (`.agents/skills/campus/SKILL.md`, installed at user level)
- ✅ SDK env bridge: `CampusClient` injects dev topology into the SDK's lazy URL resolution (live api calls need no manual `CAMPUS_*` env)
- ✅ campus-api-python pinned to versioned release wheels (currently v0.7.0); relock via the `chore(deps)` flow

---

## Project Structure
```
campus-cli/
├── main.py                 # Windows shim workaround for Poetry entry point (do not remove)
├── campus_cli/
│   ├── __init__.py
│   ├── api.py              # CampusClient wrapper (bearer + device header + SDK env bridge)
│   ├── cli.py              # Main CLI entry point (sub-app registration)
│   ├── config.py           # Configuration management
│   ├── credentials.py      # Credential storage abstraction (keyring)
│   ├── auth/               # auth + client + user + grant + vault commands
│   │   ├── common.py       # Shared utilities (confirm_destructive, dry_run_option, get_api_client)
│   │   ├── login.py        # OAuth device flow (login, logout, refresh, status)
│   │   ├── client.py       # OAuth client management (+ access sub-group)
│   │   ├── user.py         # User management
│   │   ├── grants.py       # Access-grant store (#883)
│   │   └── vault.py        # Vault commands (+ labels)
│   ├── audit/              # campus.audit commands (API-key lane)
│   │   ├── login.py, client.py, keys.py, traces.py
│   ├── resources/          # campus.api commands (#4)
│   │   ├── assignments.py, submissions.py, timetables.py, circles.py
│   │   └── files.py, hostedapps.py   # by-slug storage / app publishing
│   └── utils/
│       └── output.py       # Formatted output (table/json, dry-run Python snippets)
├── .agents/skills/campus/SKILL.md   # ZCode agent skill (source of truth)
├── tests/                  # smoke + unit run in CI; integration runs locally
├── docs/
├── .github/workflows/test.yml       # Tests matrix + tag-triggered release job
├── pyproject.toml
└── README.md
```

## Technology Stack
- **Language**: Python `>=3.11,<3.15` (3.11–3.13 security tier, CI-required; 3.14 bugfix tier, non-blocking)
- **CLI Framework**: Typer (modern, type-annotated CLI built on Click)
- **Output Formatting**: Rich for terminal output; raw spec-valid JSON for machines (#69)
- **Credential Storage**: keyring library with platform backends
- **API Client**: campus-api-python, pinned to versioned release wheels (direct URL; PyPI not viable — Warehouse rejects direct-URL deps)
- **Distribution**: GitHub Releases wheels; install via `pipx install <release wheel URL>` (see README)

## Pending Features (Not Yet Implemented)

None on the #4 parity list — the campus.api surface is fully exposed as of v0.5.0.

Known gate: `campus submission unsubmit` is shipped but the dev server rejects its null-only PATCH body — tracked upstream as campus#1071.

Candidate future work (not scoped): a `campus env show` command surfacing resolved endpoints (proposed 2026-10-01, see auth posture review); staging/prod deployments are prerequisites for any production-default flip.

---

## API Integration Notes

### campus-api-python Usage
The CLI uses the `campus_python` package, which provides:

- `Campus` class — unified client (`mode="device"` for the CLI's public-client lane)
- `auth.clients` / `auth.vaults` / `auth.users` / `auth.grants` — auth service
- `api.assignments` / `api.submissions` / `api.circles` / `api.timetable` / `api.files` / `api.hostedapps` — api service
- `audit.apikeys` / `audit.traces` — campus.audit (own API-key lane, `AuditRoot`)

### Authentication Pattern
```python
from campus_cli.auth.common import get_api_client

# Get authenticated client (with auto-refresh)
api = get_api_client()

# Access resources
clients = api.auth_clients.list()
client = api.auth_clients[client_id].get()
vault_keys = api.auth_vaults[label].keys()
assignments = api.api_assignments.list(created_by="teacher@school.edu")
```

The wrapper (`CampusClient` in `api.py`) sets the bearer on BOTH the auth
and api clients, presents the stable device id (`X-Campus-Device`), and
bridges the SDK's env-based URL resolution: the SDK ships no topology, so
the wrapper injects a bare-origin `CAMPUS_AUTH_URL` (normalizing the
CLI-facing `/auth/v1` suffix — the same variable serves both consumers)
and the dev `CAMPUS_API_URL` default. Explicit env vars always win.

### Error Handling
- API errors from `campus_python.errors` are propagated
- KeyErrors indicate missing resources (vaults, keys)
- HTTP errors are raised via `raise_for_status()`

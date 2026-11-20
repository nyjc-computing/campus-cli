# Campus CLI

Command-line interface for the Campus platform: device-flow login,
OAuth client/user/grant/vault administration, audit trace queries, and
the campus.api resources (assignments, submissions, timetables,
circles, files, hosted apps, venues). Built on the
[Campus Python SDK](https://nyjc-computing.github.io/campus-api-python/).

--8<-- "snippets/version.md"

```bash
# Authenticate (device flow — browser opens, code pre-filled)
campus auth login

# See what the stored token can do
campus auth status

# Make a first call
campus assignment list
```

## Highlights

- **Device-flow login** — no client secrets on your machine; the token
  lands in your system keyring via the SDK.
- **Every write is previewable** — pass `--dry-run` to any mutating
  command to print the equivalent Python API code without calling the
  API.
- **Machine-readable output** — `--json` always emits raw,
  spec-valid JSON (byte-exact, never soft-wrapped, #69); agents can
  force the raw form with `CAMPUS_CLI_AGENT=1`.
- **Scope-aware** — `campus auth status` reports exactly what the
  stored token can do before you hit a 403; see
  [Authentication & scopes](authentication.md).
- **Self-documenting** — this site's
  [command reference](reference/commands.md) is generated from the app
  definition itself, so it always matches `--help`.

## Where to go next

| If you want to... | Read |
|---|---|
| install the CLI | [Installation](installation.md) |
| log in, manage scopes | [Authentication & scopes](authentication.md) |
| look up any command | [Command reference](reference/commands.md) |

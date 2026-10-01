# Product Requirements Document (PRD)

## Project: campus-cli

### Overview
A command-line interface tool for interacting with the Campus API, enabling users to perform authentication, OAuth client management, and vault operations directly from the shell.

### Core Features

#### 1. Authentication Commands
- `campus auth login` - OAuth-based browser authentication
- `campus auth logout` - Clear stored credentials and revoke tokens server-side (best-effort)

#### 2. OAuth Client Management
- `campus client list` - List all OAuth clients
- `campus client new --name <name> --description <descr> [--public] [--redirect-uri <uri>]` - Create new OAuth client
- `campus client get --client-id <client_id>` - Get client details
- `campus client delete --client-id <client_id>` - Delete a client
- `campus client revoke --client-id <client_id>` - Generate a new client secret (the only time it is displayed)
- `campus client update --client-id <client_id> [--name <name>] [--description <descr>] [--redirect-uri <uri>]` - Update client metadata or replace redirect URIs

#### 3. Client Access Management
- `campus client access get --client-id <client_id> [--vault <label>]` - Get access permissions
- `campus client access grant --client-id <client_id> --vault <label> --permission <bitflag>` - Grant vault access (1=READ, 2=CREATE, 4=UPDATE, 8=DELETE)
- `campus client access revoke --client-id <client_id> --vault <label> --permission <bitflag>` - Revoke vault access
- `campus client access update --client-id <client_id> --vault <label> --permission <bitflag>` - Set (replace) a vault's access level

#### 4. Vault Management
- `campus vault list --vault <label>` - List all entries in a vault
- `campus vault get --vault <label> [--key <key>]` - Get a specific key, or the whole vault if --key is omitted
- `campus vault set --vault <label> --key <key> --value <value>` - Set key-value in vault
- `campus vault delete --vault <label> --key <key>` - Delete a key from the vault

All `client` and `vault` commands accept `--dry-run`, which prints the
equivalent `campus_python` code without authenticating or calling the API.

### Non-Functional Requirements

#### Credential Storage
- **Primary**: Native credential store (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- **Fallback**:
  - Linux: `~/.config/campus-cli/credentials.json`
  - Windows: `%USERPROFILE%\campus-cli\credentials.json`

#### Authentication Flow
- OAuth 2.0 Device Authorization Flow (RFC 8628)
- CLI requests device code and displays user code
- User enters code at verification URL in browser
- CLI polls token endpoint until authentication completes
- Stores access and refresh tokens in credential store
- Uses public client ID (`guest`) - public client type (is_public=True) stored in database

#### Logout
- Attempts server-side token revocation (RFC 7009) of the refresh and access tokens before clearing local state
- Revocation is best-effort: logout succeeds even if the auth server is unreachable or deployed without a revocation endpoint (a note is shown and only local credentials are cleared)

#### API Integration
- Uses `campus-api-python` library
- Handles API errors gracefully
- Auth endpoint resolved from `CAMPUS_AUTH_URL`, the config file, `ENV`/`CAMPUS_ENV`, or the built-in development default

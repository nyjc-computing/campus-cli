# Product Requirements Document (PRD)

## Project: campus-cli

### Overview
A command-line interface tool for interacting with the Campus API, enabling users to perform authentication and vault operations directly from the shell.

### Core Features

#### 1. Authentication Commands
- `campus auth login` - OAuth-based browser authentication
- `campus auth logout` - Clear stored credentials

#### 2. OAuth Client Management
- `campus auth client new --name <name> --description <descr>` - Create new OAuth client
- `campus auth client get --client-id <client_id>` - Get client details
- `campus auth client delete --client-id <client_id>` - Delete a client
- `campus auth client revoke --client-id <client_id>` - Revoke client access
- `campus auth client update --client-id <client_id> [--name <name>] [--description <descr>]` - Update client metadata

#### 3. Client Access Management
- `campus auth client access get --client-id <client_id>` - Get access permissions
- `campus auth client access grant --client-id <client_id>` - Grant access
- `campus auth client access revoke --client-id <client_id>` - Revoke access
- `campus auth client access update --client-id <client_id>` - Update access

#### 4. Vault Management
- `campus auth vault list --vault <label>` - List all entries in a vault
- `campus auth vault get --vault <label>` - Get entire vault
- `campus auth vault get --vault <label> --key <key>` - Get specific key from vault
- `campus auth vault set --vault <label> --key <key> --value <value>` - Set key-value in vault

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
- Uses public client ID (`uid-client-9c48f62e`) - no secret required

#### API Integration
- Uses `campus-api-python` library
- Handles API errors gracefully
- Configurable API endpoint

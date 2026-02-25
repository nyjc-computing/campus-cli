# Implementation Plan

## Project Structure
```
campus-cli/
├── campus_cli/
│   ├── __init__.py
│   ├── cli.py              # Main CLI entry point
│   ├── config.py           # Configuration management
│   ├── credentials.py      # Credential storage abstraction
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── login.py        # OAuth login flow
│   │   ├── client.py       # Client management commands
│   │   └── vault.py        # Vault commands
│   └── utils/
│       ├── __init__.py
│       └── output.py       # Formatted output (table/json)
├── tests/
├── docs/
├── .devcontainer/
├── pyproject.toml
└── README.md
```

## Technology Stack
- **Language**: Python 3.11+
- **CLI Framework**: Typer (modern, type-annotated CLI built on Click)
- **Output Formatting**: Rich for beautiful terminal output
- **Credential Storage**: keyring library with platform backends
- **API Client**: campus-api-python

## Implementation Phases

### Phase 1: Core Infrastructure
1. Create main CLI entry point with Typer
2. Set up credential storage abstraction using keyring
3. Create configuration management
4. Set up output formatting utilities (Rich)

### Phase 2: Authentication
1. Implement OAuth login flow
   - Generate authorization URL
   - Open browser for user authentication
   - Handle callback/token exchange
2. Implement logout functionality
3. Store/retrieve tokens from credential store

### Phase 3: OAuth Client Commands
1. `campus auth client new` - Create client
2. `campus auth client get` - Get client details
3. `campus auth client update` - Update client metadata
4. `campus auth client delete` - Delete client
5. `campus auth client revoke` - Revoke client access

### Phase 4: Client Access Commands
1. `campus auth client access get`
2. `campus auth client access grant`
3. `campus auth client access revoke`
4. `campus auth client access update`

### Phase 5: Vault Commands
1. `campus auth vault list`
2. `campus auth vault get` (with and without --key)
3. `campus auth vault set`

### Phase 6: Polish & Packaging
1. Error handling and user-friendly messages
2. Help text and documentation
3. Package as installable CLI tool via Poetry scripts
4. Testing

## API Integration Notes
Need to explore campus-api-python to understand:
- Available client endpoints and their signatures
- Authentication/token handling patterns
- Vault API structure
- Error handling patterns

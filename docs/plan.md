# Implementation Plan

## Project Status

**Last Updated:** 2025-03-11

### Completed
- ✅ Phase 1: Core Infrastructure (CLI entry point, credentials, config, output formatting)
- ✅ Phase 2: Authentication (OAuth device flow, logout, token storage, auto-refresh)
- ✅ Phase 3: OAuth Client Commands (list, new, get, update, delete, revoke)
- ✅ Phase 4: Client Access Commands (get, grant, revoke, update)
- ✅ Phase 5: Vault Commands (list, get, set, delete)

### In Progress / Pending
- ⏳ Phase 6: Polish & Packaging
- ⏳ API Resource Commands (timetable, assignments, circles, users)
- ⏳ Testing

---

## Project Structure
```
campus-cli/
├── campus_cli/
│   ├── __init__.py
│   ├── api.py              # Campus API client wrapper
│   ├── cli.py              # Main CLI entry point
│   ├── config.py           # Configuration management
│   ├── credentials.py      # Credential storage abstraction
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── common.py       # Shared utilities (token refresh, API client)
│   │   ├── login.py        # OAuth login flow (login, logout, refresh, status)
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

### Phase 1: Core Infrastructure ✅
1. ✅ Create main CLI entry point with Typer
2. ✅ Set up credential storage abstraction using keyring
3. ✅ Create configuration management (auth_url, auto_refresh, refresh_threshold)
4. ✅ Set up output formatting utilities (Rich)

### Phase 2: Authentication ✅
1. ✅ Implement OAuth device authorization flow
   - Request device code
   - Display user code and verification URL
   - Poll for token completion
   - Handle token refresh with auto-refresh
2. ✅ Implement logout functionality
3. ✅ Store/retrieve tokens from credential store with expiry tracking

### Phase 3: OAuth Client Commands ✅
1. ✅ `campus client list` - List all clients
2. ✅ `campus client new` - Create client
3. ✅ `campus client get` - Get client details
4. ✅ `campus client update` - Update client metadata
5. ✅ `campus client delete` - Delete client
6. ✅ `campus client revoke` - Revoke client secret

### Phase 4: Client Access Commands ✅
1. ✅ `campus client access get` - Get client vault permissions
2. ✅ `campus client access grant` - Grant vault access
3. ✅ `campus client access revoke` - Revoke vault access
4. ✅ `campus client access update` - Update vault access

### Phase 5: Vault Commands ✅
1. ✅ `campus vault list --vault <label>` - List vault keys
2. ✅ `campus vault get --vault <label> [--key <key>]` - Get vault/entry
3. ✅ `campus vault set --vault <label> --key <key> --value <value>` - Set key-value
4. ✅ `campus vault delete --vault <label> --key <key>` - Delete key

### Phase 6: Polish & Packaging ⏳
1. ⏳ Error handling and user-friendly messages
2. ⏳ Help text and documentation
3. ✅ Package as installable CLI tool via Poetry scripts
4. ⏳ Testing

## Pending Features (Not Yet Implemented)

### API Resource Commands
The following resources are available in `campus-api-python` but not yet exposed in the CLI:

#### Timetable Commands
- `campus timetable list` - List all timetables
- `campus timetable get-current` - Get current timetable ID
- `campus timetable set-current <id>` - Set current timetable
- `campus timetable get-next` - Get next timetable ID
- `campus timetable set-next <id>` - Set next timetable
- `campus timetable get <id>` - Get timetable metadata
- `campus timetable entries <id>` - List timetable entries

#### Assignment Commands
- `campus assignment list [--created-by <teacher>]` - List assignments
- `campus assignment new` - Create new assignment
- `campus assignment get <id>` - Get assignment details
- `campus assignment update <id>` - Update assignment
- `campus assignment delete <id>` - Delete assignment
- `campus assignment links add <id>` - Add classroom link

#### Circle Commands
- `campus circle list` - List circles
- `campus circle new` - Create new circle
- `campus circle get <id>` - Get circle details
- `campus circle update <id>` - Update circle
- `campus circle delete <id>` - Delete circle
- `campus circle members list <id>` - List circle members
- `campus circle members add <id> <member>` - Add member
- `campus circle members remove <id> <member>` - Remove member

#### User Commands
- `campus user list` - List users
- `campus user new` - Create new user
- `campus user get <id>` - Get user details
- `campus user activate <id>` - Activate user
- `campus user delete <id>` - Delete user

---

## API Integration Notes

### campus-api-python Usage
The CLI uses the `campus_python` package (from campus-api-python) which provides:

- `Campus` class - Unified client interface
- `auth.clients` - OAuth client management
- `auth.vaults` - Vault key-value storage
- `auth.users` - User management
- `api.timetables` - Timetable management
- `api.assignments` - Assignment management
- `api.circles` - Circle management

### Authentication Pattern
```python
from campus_cli.api import CampusClient

# Get authenticated client (with auto-refresh)
api = get_api_client()

# Access resources
clients = api.auth_clients.list()
client = api.auth_clients[client_id].get()
vault_keys = api.auth_vaults[label].keys()
```

### Error Handling
- API errors from `campus_python.errors` are propagated
- KeyErrors indicate missing resources (vaults, keys)
- HTTP errors are raised via `raise_for_status()`

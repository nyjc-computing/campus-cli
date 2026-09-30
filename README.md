# campus-cli

Command-line interface for Campus API

## Installation

```bash
git clone https://github.com/nyjc-computing/campus-cli.git
cd campus-cli
pip install .
```

This installs the `campus` command system-wide.

## Usage

```bash
# Authenticate with Campus API
campus auth login

# Create an OAuth client
campus client new --name "My App" --description "My application"

# Generate the client's secret (only time it is shown)
campus client revoke --client-id <id>

# List vault entries
campus vault list --vault myvault

# Preview any command as equivalent Python code (no API call made)
campus client new --name "My App" --description "My application" --dry-run
```

### Dry-run mode

All `client` and `vault` commands accept `--dry-run`. Instead of
authenticating and calling the API, the command prints the equivalent
Python snippet using the
[campus-api-python](https://pypi.org/project/campus-api-python/)
library — useful for learning how to call the Campus API from Python:

```python
from campus_python import Campus

campus = Campus(timeout=30, mode="device")
campus.auth.client.set_bearer_authorization("<access_token>")

client = campus.auth.clients.new(
    name='My App',
    description='My application',
)
print(client.id)
```

## Development

For development and testing, use Poetry to install the project with development dependencies:

```bash
poetry install
poetry run pytest
```

Run the CLI using `poetry run`:

```bash
poetry run campus --help
```

If you use `poetry shell` to activate the virtual environment and encounter `ModuleNotFoundError: No module named 'main'`, exit the shell and rebuild:

```bash
exit
rm -f .venv/Scripts/campus.exe .venv/Scripts/campus
poetry build && poetry install
poetry shell
```

If you don't have Poetry installed:

```bash
pip install poetry
```

## Documentation

- [Development Guide](docs/development.md) - Testing, hooks, and development workflow
- [Product Requirements](docs/PRD.md) - Product requirements document
- [Implementation Plan](docs/plan.md) - Implementation details

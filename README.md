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
campus auth client new --name "My App" --description "My application"

# List vault entries
campus auth vault list --vault myvault
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

See [docs/PRD.md](docs/PRD.md) for product requirements and [docs/plan.md](docs/plan.md) for implementation details.

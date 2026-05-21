# Development Guide

This document covers the development workflow, testing structure, and automation hooks for campus-cli.

## Prerequisites

- Python 3.11
- Poetry (for dependency management)
- Git

## Setup

```bash
# Install dependencies
poetry install

# Activate virtual environment (optional)
poetry shell
```

## Development Workflow

### Code Formatting

This project uses [ruff](https://docs.astral.sh/ruff/) for formatting and linting. Formatting is automated via Claude Code hooks (see [Hooks](#hooks) below).

Manual formatting commands:
```bash
# Format a file
poetry run ruff format <file>

# Format all files
poetry run ruff format .

# Check formatting without making changes
poetry run ruff format --check .
```

### Linting

```bash
# Run linter
poetry run ruff check .

# Fix auto-fixable issues
poetry run ruff check --fix .
```

## Testing

### Test Structure

```
tests/
├── smoke/          # Quick smoke tests (run before commits)
├── integration/    # Integration tests
└── unit/           # Unit tests
```

### Test Commands

```bash
# Run smoke tests only (fast)
poetry run pytest tests/smoke -q

# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest tests/unit/test_config.py

# Run with coverage
poetry run pytest --cov=campus_cli --cov-report=html
```

### Test Levels

| Level | Command | When it runs |
|-------|---------|--------------|
| Smoke | `poetry run pytest tests/smoke -q` | Before `git commit` (via hook) |
| Full | `poetry run pytest -q` | Before `git push` (via hook) |

## Hooks

This project uses Claude Code hooks to automate quality checks. These are configured in [`.claude/settings.local.json`](../.claude/settings.local.json).

### Available Hooks

| Hook | Trigger | Command | Purpose |
|------|---------|---------|---------|
| **post-edit** | After file write/edit | `poetry run ruff format "$FILE"` | Auto-format Python files |
| **pre-commit** | Before `git commit` | `poetry run pytest tests/smoke -q` | Run quick smoke tests |
| **pre-push** | Before `git push` | `poetry run pytest -q` | Run full test suite |

### Hook Behavior

- **post-edit**: Runs immediately after any file is written or edited. Formats the file using ruff.
- **pre-commit**: Blocks commit if smoke tests fail. Tests run quietly (`-q` flag).
- **pre-push**: Blocks push if any test fails. Full test suite runs quietly.

### Bypassing Hooks

If you need to bypass hooks temporarily:

```bash
# Skip pre-commit hook
git commit --no-verify

# Skip pre-push hook
git push --no-verify
```

Use `--no-verify` sparingly and only when you have a good reason (e.g., documentation-only commits).

## Project Structure

```
campus-cli/
├── campus_cli/           # Main package
│   ├── __init__.py
│   ├── cli.py            # CLI entry point (Typer app)
│   ├── config.py         # Configuration management
│   └── credentials.py    # Credential storage
├── tests/                # Test suite
├── docs/                 # Documentation
├── .claude/              # Claude Code configuration
│   └── settings.local.json  # Hooks and permissions
├── pyproject.toml        # Poetry configuration
└── README.md
```

## Common Tasks

### Adding a New CLI Command

1. Define the command in `campus_cli/cli.py` using Typer decorators
2. Add unit tests in `tests/unit/`
3. Add integration tests in `tests/integration/` (if applicable)
4. Run `poetry run ruff format .` to format new code
5. Run `poetry run pytest` to verify tests pass

### Updating Dependencies

```bash
# Update a specific dependency
poetry add package_name@latest

# Update all dependencies
poetry update

# Lock file changes (commit poetry.lock)
git add poetry.lock pyproject.toml
git commit -m "chore: update dependencies"
```

### Debugging Tests

```bash
# Run with pdb debugger
poetry run pytest --pdb

# Show print output
poetry run pytest -s

# Stop on first failure
poetry run pytest -x

# Run specific test with verbose output
poetry run pytest -v tests/unit/test_config.py::test_function_name
```

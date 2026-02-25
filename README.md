# campus-cli

Command-line interface for Campus API

## Installation

```bash
pip install campus-cli
```

## Usage

```bash
campus auth login
campus auth client new --name "My App" --description "My application"
campus auth vault list --vault myvault
```

## Documentation

See [docs/PRD.md](docs/PRD.md) for product requirements and [docs/plan.md](docs/plan.md) for implementation details.

## Development

```bash
poetry install
poetry run campus --help
```

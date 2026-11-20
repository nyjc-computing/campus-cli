# Installation

Install a versioned release with [pipx](https://pipx.pypa.io)
(recommended — isolated venv, the `campus` command on your PATH):

```bash
pipx install https://github.com/nyjc-computing/campus-cli/releases/download/v0.8.0/campus_cli-0.8.0-py3-none-any.whl
```

or with pip into your Python environment:

```bash
pip install https://github.com/nyjc-computing/campus-cli/releases/download/v0.8.0/campus_cli-0.8.0-py3-none-any.whl
```

Releases are tagged `vX.Y.Z`; swap the URL for the version you want —
see the [releases page](https://github.com/nyjc-computing/campus-cli/releases)
(the [landing page](index.md) stamp also links the current one). Every
release wheel carries the pinned `campus-api-python` release it was
tested against — pip resolves it from GitHub Releases automatically,
so no git and no source checkout are needed.

Python 3.11–3.13 are officially supported; 3.14 runs for signal only.

## Development

```bash
git clone https://github.com/nyjc-computing/campus-cli.git
cd campus-cli
poetry install
poetry run campus version
```

After changing any command surface, regenerate the committed docs
artifacts (CI fails on drift — see AGENTS.md):

```bash
poetry run python scripts/generate_cli_reference.py
poetry run python scripts/sync_docs_version.py
poetry run mkdocs build --strict
```

# campus-cli Quick Reference

The user-facing `campus` command line for the Campus platform. Docs
are a MkDocs Material site published to GitHub Pages, with a command
reference **generated from the Typer app** — the committed-artifact +
drift-gate pattern the campus suite uses for its OpenAPI specs.

## Docs workflow

```bash
poetry run python scripts/generate_cli_reference.py  # docs/reference/commands.md
poetry run python scripts/sync_docs_version.py       # docs/snippets/version.md
poetry run mkdocs build --strict                     # docs-rot gate (CI runs this on every PR)
poetry run mkdocs serve                              # local preview at http://127.0.0.1:8000
```

- Command help IS documentation: the reference renders each command's
  docstring/help and every option's `help=`. When you add or change a
  command, write the help text you want users to read — then
  regenerate.
- CI regenerates both artifacts and fails on `git diff --exit-code --
  docs/`, and `mkdocs build --strict` fails on broken links. Forgetting
  to regenerate cannot merge.

## Version bumps must ship with up-to-date docs

**Rule: every version bump must have up-to-date docs.** After
`poetry version ...`:

1. `poetry run python scripts/sync_docs_version.py` — regenerate the
   landing-page stamp.
2. `poetry run python scripts/generate_cli_reference.py` — pick up any
   command surface changes.
3. Update `docs/*.md` guides and the README install snippet if they
   pin an old wheel version.
4. Commit everything together, then cut the release
   (`git tag -a vX.Y.Z -m "<notes>"`; the tag annotation is the
   release body) — the docs stamp and the release must carry the same
   version.

CI enforces the stamp/reference freshness on every PR to main.

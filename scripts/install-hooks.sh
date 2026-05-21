#!/bin/bash
# Install git hooks for this project

set -e

HOOKS_DIR=".git/hooks"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing git hooks..."

# Create post-edit hook
cat > "$HOOKS_DIR/post-edit" <<'EOF'
#!/bin/bash
# post-edit hook - run ruff formatter on the edited file

# Get the file that was edited (passed as argument)
FILE="$1"

# Only process Python files
if [[ "$FILE" == *.py ]]; then
    # Run ruff format on the file
    ".\.venv\Scripts\poetry.exe" run ruff format "$FILE"
fi
EOF
chmod +x "$HOOKS_DIR/post-edit"

# Create pre-commit hook
cat > "$HOOKS_DIR/pre-commit" <<'EOF'
#!/bin/bash
# pre-commit hook - run smoke tests

set -e

echo "Running smoke tests..."
".\.venv\Scripts\poetry.exe" run pytest tests/smoke/ -v --tb=short

echo "Smoke tests passed!"
EOF
chmod +x "$HOOKS_DIR/pre-commit"

# Create pre-push hook
cat > "$HOOKS_DIR/pre-push" <<'EOF'
#!/bin/bash
# pre-push hook - run ruff check

set -e

echo "Running ruff check..."
".\.venv\Scripts\poetry.exe" run ruff check .

echo "Ruff check passed!"
EOF
chmod +x "$HOOKS_DIR/pre-push"

echo "Git hooks installed successfully!"
echo "Hooks installed:"
echo "  - post-edit: Run ruff format on edited Python files"
echo "  - pre-commit: Run smoke tests before committing"
echo "  - pre-push: Run ruff check before pushing"

# Install git hooks for this project

$ErrorActionPreference = "Stop"

$HooksDir = ".git/hooks"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Installing git hooks..." -ForegroundColor Green

# Create post-edit hook
$postEditContent = @"
#!/bin/bash
# post-edit hook - run ruff formatter on the edited file

# Get the file that was edited (passed as argument)
FILE="`$1"

# Only process Python files
if [[ "`$FILE" == *.py ]]; then
    # Run ruff format on the file
    poetry run ruff format "`$FILE"
fi
"@
Set-Content -Path "$HooksDir/post-edit" -Value $postEditContent -NoNewline

# Create pre-commit hook
$preCommitContent = @"
#!/bin/bash
# pre-commit hook - run smoke tests

set -e

echo "Running smoke tests..."
poetry run pytest tests/smoke/ -v --tb=short

echo "Smoke tests passed!"
"@
Set-Content -Path "$HooksDir/pre-commit" -Value $preCommitContent -NoNewline

# Create pre-push hook
$prePushContent = @"
#!/bin/bash
# pre-push hook - run ruff check

set -e

echo "Running ruff check..."
poetry run ruff check .

echo "Ruff check passed!"
"@
Set-Content -Path "$HooksDir/pre-push" -Value $prePushContent -NoNewline

Write-Host "Git hooks installed successfully!" -ForegroundColor Green
Write-Host "Hooks installed:" -ForegroundColor Cyan
Write-Host "  - post-edit: Run ruff format on edited Python files"
Write-Host "  - pre-commit: Run smoke tests before committing"
Write-Host "  - pre-push: Run ruff check before pushing"

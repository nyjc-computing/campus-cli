"""Unit tests for vault commands (#75)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


def _api(labels):
    """An API client whose vaults.labels() returns the given labels."""
    api = MagicMock()
    api.auth_vaults.labels.return_value = labels
    return api


def test_vault_labels_lists_labels():
    with patch("campus_cli.auth.vault.get_api_client") as mock_get:
        mock_get.return_value = _api(["email", "settings"])
        result = runner.invoke(app, ["vault", "labels"])
    assert result.exit_code == 0, result.stdout
    assert "email" in result.stdout
    assert "settings" in result.stdout


def test_vault_labels_json():
    with patch("campus_cli.auth.vault.get_api_client") as mock_get:
        mock_get.return_value = _api(["email"])
        result = runner.invoke(app, ["vault", "labels", "--json"])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == {"labels": ["email"], "count": 1}


def test_vault_labels_empty():
    with patch("campus_cli.auth.vault.get_api_client") as mock_get:
        mock_get.return_value = _api([])
        result = runner.invoke(app, ["vault", "labels"])
    assert result.exit_code == 0, result.stdout


def test_vault_labels_dry_run_never_touches_api():
    with patch("campus_cli.auth.vault.get_api_client") as mock_get:
        result = runner.invoke(app, ["vault", "labels", "--dry-run"])
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "vaults.labels()" in result.stdout

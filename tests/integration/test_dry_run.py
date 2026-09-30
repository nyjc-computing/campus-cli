"""Integration tests for the --dry-run flag.

Dry-run must show the equivalent campus_python code WITHOUT
authenticating or calling the API.
"""

import contextlib
from unittest.mock import patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()

CLIENT_MODULES = ("campus_cli.auth.client", "campus_cli.auth.vault")


def _invoke_dry_run(*args):
    """Invoke a dry-run command, failing if the API client was touched."""
    with contextlib.ExitStack() as stack:
        api_mocks = [
            stack.enter_context(patch(f"{module}.get_api_client"))
            for module in CLIENT_MODULES
        ]
        result = runner.invoke(app, [*args, "--dry-run"])
        for mock_get in api_mocks:
            mock_get.assert_not_called()
    assert result.exit_code == 0
    assert "Dry run" in result.stdout
    assert "campus_python import Campus" in result.stdout
    assert "set_bearer_authorization" in result.stdout
    return result


def test_client_new_dry_run():
    """client new --dry-run shows the clients.new() call with arguments."""
    result = _invoke_dry_run(
        "client", "new", "--name", "My App", "--description", "Test app"
    )

    assert "campus.auth.clients.new(" in result.stdout
    assert "name='My App'" in result.stdout
    assert "description='Test app'" in result.stdout


def test_client_new_dry_run_public_options():
    """Public-client options appear in the dry-run snippet only if passed."""
    result = _invoke_dry_run(
        "client", "new",
        "--name", "Pub", "--description", "Public app",
        "--public", "--redirect-uri", "https://a/cb",
    )

    assert "is_public=True" in result.stdout
    assert "redirect_uris=['https://a/cb']" in result.stdout

    plain = _invoke_dry_run("client", "new", "--name", "A", "--description", "B")
    # The minimal snippet omits kwargs the command would leave at defaults
    assert "is_public" not in plain.stdout
    assert "redirect_uris" not in plain.stdout


def test_client_get_dry_run():
    """client get --dry-run shows indexed resource access."""
    result = _invoke_dry_run("client", "get", "--client-id", "uid-client-x")

    assert "campus.auth.clients['uid-client-x'].get()" in result.stdout


def test_client_list_dry_run():
    """client list --dry-run shows clients.list()."""
    result = _invoke_dry_run("client", "list")

    assert "campus.auth.clients.list()" in result.stdout


def test_client_update_dry_run_only_passed_fields():
    """client update --dry-run shows only the fields being updated."""
    result = _invoke_dry_run(
        "client", "update", "--client-id", "uid-x", "--name", "New Name"
    )

    assert "campus.auth.clients['uid-x'].update(" in result.stdout
    assert "name='New Name'" in result.stdout
    assert "description=" not in result.stdout


def test_client_delete_dry_run_skips_confirmation():
    """client delete --dry-run shows the delete call without prompting."""
    result = _invoke_dry_run("client", "delete", "--client-id", "uid-x")

    assert "campus.auth.clients['uid-x'].delete()" in result.stdout
    assert "Are you sure" not in result.stdout


def test_client_revoke_dry_run():
    """client revoke --dry-run shows the revoke call."""
    result = _invoke_dry_run("client", "revoke", "--client-id", "uid-x")

    assert "campus.auth.clients['uid-x'].revoke()" in result.stdout


def test_client_access_grant_dry_run():
    """client access grant --dry-run shows the grant call."""
    result = _invoke_dry_run(
        "client", "access", "grant",
        "--client-id", "uid-x", "--vault", "myvault", "--permission", "3",
    )

    assert "campus.auth.clients['uid-x'].access.grant(" in result.stdout
    assert "vault='myvault', permission=3," in result.stdout


def test_client_access_get_dry_run_without_vault():
    """client access get --dry-run omits the vault kwarg when not given."""
    result = _invoke_dry_run("client", "access", "get", "--client-id", "uid-x")

    assert "access.get()" in result.stdout


def test_vault_set_dry_run():
    """vault set --dry-run shows the item assignment."""
    result = _invoke_dry_run(
        "vault", "set",
        "--vault", "myvault", "--key", "api_key", "--value", "s3cr3t",
    )

    assert "campus.auth.vaults['myvault']['api_key'] = 's3cr3t'" in result.stdout


def test_vault_get_dry_run_with_key():
    """vault get --dry-run with --key shows single-key access."""
    result = _invoke_dry_run(
        "vault", "get", "--vault", "myvault", "--key", "api_key"
    )

    assert "campus.auth.vaults['myvault']['api_key']" in result.stdout


def test_vault_get_dry_run_whole_vault():
    """vault get --dry-run without --key shows iteration over keys."""
    result = _invoke_dry_run("vault", "get", "--vault", "myvault")

    assert "campus.auth.vaults['myvault'].keys()" in result.stdout


def test_vault_delete_dry_run_skips_confirmation():
    """vault delete --dry-run shows the del statement without prompting."""
    result = _invoke_dry_run(
        "vault", "delete", "--vault", "myvault", "--key", "api_key"
    )

    assert "del campus.auth.vaults['myvault']['api_key']" in result.stdout
    assert "Are you sure" not in result.stdout


def test_vault_list_dry_run():
    """vault list --dry-run shows vault.keys()."""
    result = _invoke_dry_run("vault", "list", "--vault", "myvault")

    assert "campus.auth.vaults['myvault'].keys()" in result.stdout


def test_dry_run_flag_documented_in_help():
    """--dry-run appears in help for API-backed command groups."""
    for group_args in (["client"], ["vault"]):
        result = runner.invoke(app, [*group_args, "list", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.stdout


def test_dry_run_without_authentication():
    """--dry-run works when not logged in (no token lookup)."""
    with patch("campus_cli.auth.common.credentials") as mock_creds:
        result = _invoke_dry_run(
            "vault", "set",
            "--vault", "v", "--key", "k", "--value", "val",
        )
        mock_creds.get_token.assert_not_called()

    assert "campus.auth.vaults['v']['k'] = 'val'" in result.stdout


def _extract_snippet(stdout: str) -> str:
    """Extract the Python code block from dry-run output."""
    lines = stdout.splitlines()
    start = next(
        i for i, line in enumerate(lines)
        if line.startswith("Equivalent Python code for")
    ) + 1
    end = next(
        i for i, line in enumerate(lines)
        if "Requires the campus-api-python" in line
    )
    return "\n".join(lines[start:end])


def test_dry_run_snippets_are_valid_python():
    """Generated snippets compile for representative commands."""
    cases = [
        ("client", "new", "--name", "A", "--description", "B"),
        ("client", "get", "--client-id", "uid-x"),
        ("client", "revoke", "--client-id", "uid-x"),
        ("client", "access", "grant", "--client-id", "uid-x",
         "--vault", "v", "--permission", "3"),
        ("vault", "get", "--vault", "myvault"),
        ("vault", "get", "--vault", "myvault", "--key", "k"),
        ("vault", "delete", "--vault", "myvault", "--key", "k"),
    ]
    for case in cases:
        result = _invoke_dry_run(*case)
        code = _extract_snippet(result.stdout)
        compile(code, f"<dry-run: {' '.join(case)}>", "exec")


def test_dry_run_quotes_tricky_values():
    """Values containing quotes are escaped in the snippet."""
    result = _invoke_dry_run(
        "vault", "set",
        "--vault", "myvault", "--key", "greeting", "--value", 'he said "hi"',
    )

    assert 'campus.auth.vaults[\'myvault\'][\'greeting\'] = \'he said "hi"\'' \
        in result.stdout
    code = _extract_snippet(result.stdout)
    compile(code, "<dry-run: tricky value>", "exec")

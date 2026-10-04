"""OAuth client management commands."""

import typer
from rich.console import Console

from campus_cli.auth.common import (
    confirm_destructive,
    dry_run_option,
    get_api_client,
)
from campus_cli.utils.output import (
    print_error,
    print_json,
    print_python_api,
    print_success,
)

client_app = typer.Typer(help="OAuth client management commands")
console = Console()


def _format_client(client) -> dict:
    """Format a client model for output.

    Args:
        client: The campus.model.Client instance

    Returns:
        Dict representation of the client
    """
    # created_at arrives as a datetime when constructed locally but as an
    # ISO string via Client.from_resource (the API layer does not coerce).
    created_at = client.created_at
    return {
        "id": client.id,
        "name": client.name,
        "description": client.description,
        "created_at": (
            created_at.isoformat()
            if hasattr(created_at, "isoformat")
            else created_at
        ),
        "permissions": client.permissions,
        # /authorize will exact-match redirect_uri (RFC 6749 §3.1.2.2),
        # so admins need to see which clients have none registered.
        "redirect_uris": client.redirect_uris or [],
        "is_public": client.is_public,
        # Fail-closed admin fields (docs/auth-token-invariants.md A1/B3/C1):
        # admins vetting a client need to see exactly what it may hold.
        "allowed_scopes": client.allowed_scopes or [],
        "upstream_scopes": client.upstream_scopes or {},
        "token_bridge": bool(client.token_bridge),
    }


def _print_client_details(client_data: dict) -> None:
    """Print client details in a formatted way.

    Args:
        client_data: Dict with client information
    """
    console.print(f"[bold]Client ID:[/bold] {client_data.get('id', 'N/A')}")
    console.print(f"[bold]Name:[/bold] {client_data.get('name', 'N/A')}")
    console.print(f"[bold]Description:[/bold] {client_data.get('description', 'N/A')}")

    if client_data.get("created_at"):
        console.print(f"[bold]Created:[/bold] {client_data['created_at']}")

    if client_data.get("permissions"):
        console.print("[bold]Permissions:[/bold]")
        for vault, access in client_data["permissions"].items():
            console.print(f"  - {vault}: {access}")

    _print_client_redirect_uris(client_data)
    _print_client_scopes(client_data)


def _print_client_redirect_uris(client_data: dict, indent: str = "") -> None:
    """Print redirect URIs one per line, plus the public-client flag."""
    uris = client_data.get("redirect_uris") or []
    console.print(f"{indent}[bold]Redirect URIs:[/bold]")
    if uris:
        for uri in uris:
            console.print(f"{indent}  - {uri}")
    else:
        console.print(f"{indent}  (none)")
    console.print(
        f"{indent}[bold]Public client:[/bold] "
        f"{'yes' if client_data.get('is_public') else 'no'}"
    )


def _print_client_scopes(client_data: dict, indent: str = "") -> None:
    """Print the scope allowlists and token-bridge flag."""
    allowed = client_data.get("allowed_scopes") or []
    console.print(f"{indent}[bold]Allowed scopes:[/bold]")
    if allowed:
        for scope in allowed:
            console.print(f"{indent}  - {scope}")
    else:
        console.print(f"{indent}  (none)")
    upstream = client_data.get("upstream_scopes") or {}
    console.print(f"{indent}[bold]Upstream scopes:[/bold]")
    if upstream:
        for provider, scopes in upstream.items():
            console.print(f"{indent}  {provider}:")
            for scope in scopes:
                console.print(f"{indent}    - {scope}")
    else:
        console.print(f"{indent}  (none)")
    console.print(
        f"{indent}[bold]Token bridge:[/bold] "
        f"{'yes' if client_data.get('token_bridge') else 'no'}"
    )


@client_app.command("list")
def client_list(
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    List all OAuth clients.

    Displays all OAuth clients with their IDs, names, and descriptions.
    """
    if dry_run:
        print_python_api(
            "campus client list",
            [
                "clients = campus.auth.clients.list()",
                "for client in clients:",
                "    print(client.id, client.name)",
            ],
        )
        return

    try:
        api = get_api_client()
        clients = api.auth_clients.list()

        if output_json:
            print_json([_format_client(c) for c in clients])
        else:
            if not clients:
                console.print("[dim]No clients found.[/dim]")
                return

            console.print(f"[bold]Found {len(clients)} client(s):[/bold]\n")
            for client in clients:
                console.print(f"[cyan]{client.id}[/cyan]")
                console.print(f"  Name: {client.name}")
                console.print(f"  Description: {client.description}")
                _print_client_redirect_uris(_format_client(client), indent="  ")
                if client.permissions:
                    vaults = ", ".join(client.permissions.keys())
                    console.print(f"  Vaults: {vaults}")
                console.print()

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to list clients: {e}")
        raise typer.Exit(1) from e


@client_app.command("new")
def client_new(
    name: str = typer.Option(
        ..., "--name", "-n", help="Client name"
    ),
    description: str = typer.Option(
        ..., "--description", "-d", help="Client description"
    ),
    is_public: bool = typer.Option(
        False,
        "--public",
        help="Create a public client (no client secret, per RFC 6749 §2.1)",
    ),
    redirect_uri: list[str] = typer.Option(  # noqa: B008
        [],
        "--redirect-uri",
        help="OAuth redirect URI for the client (repeat for multiple;"
        " typically used with --public)",
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Create a new OAuth client.

    Creates a new OAuth client with the specified name and description.
    By default the client is confidential: the client secret is NOT
    returned; use 'campus client revoke' to generate and retrieve it.
    Public clients (--public) have no client secret at all.
    """
    if dry_run:
        new_kwargs = [
            f"name={name!r}",
            f"description={description!r}",
        ]
        if is_public:
            new_kwargs.append("is_public=True")
        if redirect_uri:
            new_kwargs.append(f"redirect_uris={list(redirect_uri)!r}")
        print_python_api(
            "campus client new",
            [
                "client = campus.auth.clients.new(",
                *(f"    {kwarg}," for kwarg in new_kwargs),
                ")",
                "print(client.id)",
            ],
        )
        return

    try:
        api = get_api_client()
        client = api.auth_clients.new(
            name=name,
            description=description,
            is_public=is_public,
            redirect_uris=list(redirect_uri) or None,
        )

        result = _format_client(client)

        if output_json:
            print_json(result)
        else:
            print_success(f"Client '{name}' created successfully!")
            _print_client_details(result)
            if client.is_public:
                console.print(
                    "\n[dim]Public client: no client secret"
                    " (RFC 6749 §2.1).[/dim]"
                )
            else:
                console.print(
                    "\n[yellow]Note: Use 'campus client revoke' to "
                    "generate the client secret.[/yellow]"
                )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to create client: {e}")
        raise typer.Exit(1) from e


@client_app.command("get")
def client_get(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Get details of an OAuth client.

    Retrieves and displays information about the specified client.
    Note: The client secret is NOT displayed.
    """
    if dry_run:
        print_python_api(
            "campus client get",
            [
                f"client = campus.auth.clients[{client_id!r}].get()",
                "print(client.name, client.description)",
            ],
        )
        return

    try:
        api = get_api_client()
        client = api.auth_clients[client_id].get()

        result = _format_client(client)

        if output_json:
            print_json(result)
        else:
            _print_client_details(result)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get client: {e}")
        raise typer.Exit(1) from e


def _group_upstream_scopes(values: list[str]) -> dict[str, list[str]]:
    """Group repeated --upstream-scope values by provider.

    Each value must be `provider=scope`; the scope URL may contain '='.
    Providers keep first-seen order; scopes keep flag order.
    """
    grouped: dict[str, list[str]] = {}
    for value in values:
        provider, sep, scope = value.partition("=")
        if not sep or not provider or not scope:
            print_error(
                f"Invalid --upstream-scope {value!r}: expected"
                " provider=scope (e.g."
                " google=https://www.googleapis.com/auth/classroom.rosters)."
            )
            raise typer.Exit(1)
        grouped.setdefault(provider, []).append(scope)
    return grouped


@client_app.command("update")
def client_update(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    name: str | None = typer.Option(None, "--name", "-n", help="New client name"),
    description: str | None = typer.Option(
        None, "--description", "-d", help="New client description"
    ),
    redirect_uri: list[str] = typer.Option(  # noqa: B008
        [],
        "--redirect-uri",
        help="OAuth redirect URI (repeat for multiple; REPLACES the existing"
        " list, so re-pass the full list when adding one)",
    ),
    allowed_scope: list[str] = typer.Option(  # noqa: B008
        [],
        "--allowed-scope",
        help="Scope this client may be granted on campus tokens (repeat for"
        " multiple; REPLACES the whole allowlist, so re-pass every scope the"
        " client must keep). Fail-closed: an empty allowlist grants nothing",
    ),
    clear_allowed_scopes: bool = typer.Option(
        False,
        "--clear-allowed-scopes",
        help="Empty the scope allowlist (fail-closed: grants nothing)",
    ),
    upstream_scope: list[str] = typer.Option(  # noqa: B008
        [],
        "--upstream-scope",
        help="Upstream scope as provider=scope (repeat for multiple;"
        " scopes of the same provider are grouped; REPLACES the whole"
        " upstream scope map, so re-pass every provider=scope pair the"
        " client must keep)",
    ),
    token_bridge: bool | None = typer.Option(  # noqa: B008
        None,
        "--token-bridge/--no-token-bridge",
        help="Grant/revoke broker token-bridge access (confidential clients"
        " only; the server rejects it for public clients)",
    ),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Update an OAuth client.

    Updates the name, description, redirect URIs, scope allowlists and/or
    token-bridge access of an existing client. List-valued options
    (--redirect-uri, --allowed-scope, --upstream-scope) REPLACE the whole
    stored value: the API layer full-replaces each provided field, so
    re-pass every entry the client must keep. Fields you omit are left
    untouched.
    """
    if clear_allowed_scopes and allowed_scope:
        print_error(
            "--clear-allowed-scopes cannot be combined with --allowed-scope."
        )
        raise typer.Exit(1)

    upstream_scopes = _group_upstream_scopes(list(upstream_scope))

    if not (name or description or redirect_uri or allowed_scope
            or clear_allowed_scopes or upstream_scope
            or token_bridge is not None):
        print_error(
            "At least one of --name, --description, --redirect-uri,"
            " --allowed-scope, --clear-allowed-scopes, --upstream-scope or"
            " --token-bridge must be provided."
        )
        raise typer.Exit(1)

    if dry_run:
        update_kwargs = []
        if name:
            update_kwargs.append(f"name={name!r}")
        if description:
            update_kwargs.append(f"description={description!r}")
        if redirect_uri:
            update_kwargs.append(f"redirect_uris={list(redirect_uri)!r}")
        if allowed_scope:
            update_kwargs.append(f"allowed_scopes={list(allowed_scope)!r}")
        if clear_allowed_scopes:
            update_kwargs.append("allowed_scopes=[]")
        if upstream_scope:
            update_kwargs.append(f"upstream_scopes={upstream_scopes!r}")
        if token_bridge is not None:
            update_kwargs.append(f"token_bridge={token_bridge}")
        print_python_api(
            "campus client update",
            [
                f"client = campus.auth.clients[{client_id!r}].update(",
                *(f"    {kwarg}," for kwarg in update_kwargs),
                ")",
                "print(client.name, client.description)",
            ],
        )
        return

    try:
        api = get_api_client()
        update_kwargs: dict = {}
        if name:
            update_kwargs["name"] = name
        if description:
            update_kwargs["description"] = description
        if redirect_uri:
            update_kwargs["redirect_uris"] = list(redirect_uri)
        if allowed_scope:
            update_kwargs["allowed_scopes"] = list(allowed_scope)
        elif clear_allowed_scopes:
            update_kwargs["allowed_scopes"] = []
        if upstream_scope:
            update_kwargs["upstream_scopes"] = upstream_scopes
        if token_bridge is not None:
            update_kwargs["token_bridge"] = token_bridge
        client = api.auth_clients[client_id].update(**update_kwargs)

        result = _format_client(client)

        if output_json:
            print_json(result)
        else:
            print_success(f"Client '{client_id}' updated successfully!")
            _print_client_details(result)

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update client: {e}")
        raise typer.Exit(1) from e


@client_app.command("delete")
def client_delete(
    client_id: str = typer.Option(
        ..., "--client-id", "-i", help="Client ID"
    ),
    confirm: bool = typer.Option(
        False, "--confirm", "-y", help="Skip confirmation"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Delete an OAuth client.

    Permanently deletes the specified OAuth client.
    """
    if dry_run:
        print_python_api(
            "campus client delete",
            [f"campus.auth.clients[{client_id!r}].delete()"],
        )
        return

    confirm_destructive(f"delete client '{client_id}'", confirm)

    try:
        api = get_api_client()
        api.auth_clients[client_id].delete()
        print_success(f"Client '{client_id}' deleted successfully.")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to delete client: {e}")
        raise typer.Exit(1) from e


@client_app.command("revoke")
def client_revoke(
    client_id: str = typer.Option(..., "--client-id", "-i", help="Client ID"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Generate a new client secret.

    Revokes the current client secret and generates a new one.
    The new secret will be displayed (this is the only way to retrieve it).
    Use this when first creating a client or when you need to rotate the secret.
    """
    if dry_run:
        print_python_api(
            "campus client revoke",
            [
                f"secret = campus.auth.clients[{client_id!r}].revoke()",
                "print(secret)",
            ],
        )
        return

    confirm_destructive(
        f"revoke and regenerate the secret for client '{client_id}'", confirm
    )

    try:
        api = get_api_client()
        new_secret = api.auth_clients[client_id].revoke()

        if output_json:
            print_json({"client_id": client_id, "secret": new_secret})
        else:
            print_success(f"New secret generated for client '{client_id}'.")
            console.print(
                f"[bold]Client Secret:[/bold] "
                f"[bold yellow]{new_secret}[/bold yellow]"
            )
            console.print(
                "\n[yellow]Note: Store this secret securely. "
                "It won't be shown again.[/yellow]"
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to revoke client: {e}")
        raise typer.Exit(1) from e


# Client access sub-commands
access_app = typer.Typer(help="OAuth client access management commands")
client_app.add_typer(access_app, name="access")


@access_app.command("get")
def client_access_get(
    client_id: str = typer.Option(
        ..., "--client-id", "-i", help="Client ID"
    ),
    vault: str | None = typer.Option(
        None, "--vault", "-v",
        help="Vault label (if not specified, shows all)"
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Get client vault access permissions.

    Displays the access permissions for a client.
    If --vault is specified, shows only that vault's permissions.
    Otherwise, shows all vault permissions.
    """
    if dry_run:
        vault_arg = f"vault={vault!r}" if vault else ""
        print_python_api(
            "campus client access get",
            [
                f"access = campus.auth.clients[{client_id!r}]"
                f".access.get({vault_arg})",
                "print(access)",
            ],
        )
        return

    try:
        api = get_api_client()
        access = api.auth_clients[client_id].access.get(vault=vault)

        if output_json:
            print_json(access)
        else:
            if vault:
                console.print(f"[bold]Client:[/bold] {client_id}")
                console.print(f"[bold]Vault:[/bold] {vault}")
                console.print(f"[bold]Access:[/bold] {access.get('access', 'N/A')}")
            else:
                console.print(f"[bold]Client:[/bold] {client_id}")
                console.print("[bold]Vault Access:[/bold]")
                if not access.get("access"):
                    console.print("[dim]No vault access configured.[/dim]")
                else:
                    for vault_label, access_level in access["access"].items():
                        console.print(f"  {vault_label}: {access_level}")

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to get client access: {e}")
        raise typer.Exit(1) from e


@access_app.command("grant")
def client_access_grant(
    client_id: str = typer.Option(
        ..., "--client-id", "-i", help="Client ID"
    ),
    vault: str = typer.Option(
        ..., "--vault", "-v", help="Vault label"
    ),
    permission: int = typer.Option(
        ..., "--permission", "-p",
        help="Permission bitflag (1=READ, 2=CREATE, 4=UPDATE, 8=DELETE)"
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Grant vault access to a client.

    Grants the specified permission level for a vault to the client.
    Permissions are bitflags: 1=READ, 2=CREATE, 4=UPDATE, 8=DELETE.
    Combine with bitwise OR: e.g., 3 for READ+CREATE.
    """
    if dry_run:
        print_python_api(
            "campus client access grant",
            [
                f"campus.auth.clients[{client_id!r}].access.grant(",
                f"    vault={vault!r}, permission={permission},",
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        result = api.auth_clients[client_id].access.grant(
            vault=vault, permission=permission
        )

        if output_json:
            print_json(result)
        else:
            print_success(
                f"Granted access to vault '{vault}' for client '{client_id}'."
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to grant client access: {e}")
        raise typer.Exit(1) from e


@access_app.command("revoke")
def client_access_revoke(
    client_id: str = typer.Option(
        ..., "--client-id", "-i", help="Client ID"
    ),
    vault: str = typer.Option(
        ..., "--vault", "-v", help="Vault label"
    ),
    permission: int = typer.Option(
        ..., "--permission", "-p", help="Permission bitflag to revoke"
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Revoke vault access from a client.

    Revokes the specified permission level for a vault from the client.
    Permissions are bitflags: 1=READ, 2=CREATE, 4=UPDATE, 8=DELETE.
    """
    if dry_run:
        print_python_api(
            "campus client access revoke",
            [
                f"campus.auth.clients[{client_id!r}].access.revoke(",
                f"    vault={vault!r}, permission={permission},",
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        result = api.auth_clients[client_id].access.revoke(
            vault=vault, permission=permission
        )

        if output_json:
            print_json(result)
        else:
            print_success(
                f"Revoked access to vault '{vault}' for client '{client_id}'."
            )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to revoke client access: {e}")
        raise typer.Exit(1) from e


@access_app.command("update")
def client_access_update(
    client_id: str = typer.Option(
        ..., "--client-id", "-i", help="Client ID"
    ),
    vault: str = typer.Option(
        ..., "--vault", "-v", help="Vault label"
    ),
    permission: int = typer.Option(
        ..., "--permission", "-p", help="Permission bitflag to set"
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
    dry_run: bool = dry_run_option(),
) -> None:
    """
    Update (replace) vault access for a client.

    Sets the permission level for a vault to the exact value specified.
    Use 0 to remove all access to the vault.
    Permissions are bitflags: 1=READ, 2=CREATE, 4=UPDATE, 8=DELETE.
    """
    if dry_run:
        print_python_api(
            "campus client access update",
            [
                f"campus.auth.clients[{client_id!r}].access.update(",
                f"    vault={vault!r}, permission={permission},",
                ")",
            ],
        )
        return

    try:
        api = get_api_client()
        result = api.auth_clients[client_id].access.update(
            vault=vault, permission=permission
        )

        if output_json:
            print_json(result)
        else:
            if permission == 0:
                print_success(
                    f"Removed all access to vault '{vault}' "
                    f"for client '{client_id}'."
                )
            else:
                print_success(
                    f"Updated access to vault '{vault}' for client '{client_id}'."
                )

    except typer.Exit:
        raise
    except Exception as e:
        print_error(f"Failed to update client access: {e}")
        raise typer.Exit(1) from e

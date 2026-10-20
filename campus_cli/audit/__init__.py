"""campus.audit commands (#54).

The audit service (/audit/v1) is a separate, user-blind deployment
authenticating with its own API keys (`audit_v1_...`, Bearer) rather
than OAuth user tokens. The command group mirrors its two
capabilities: the operator's key lifecycle (campus audit keys) and
read-only trace queries (campus audit traces), plus login/logout over
the stored key — the CLI's only non-OAuth credential.
"""

import typer

from campus_cli.audit.keys import keys_app
from campus_cli.audit.login import login_cmd, logout_cmd
from campus_cli.audit.traces import traces_app

audit_app = typer.Typer(help="Campus Audit service commands (API-key auth)")

# login/logout attach directly; keys and traces are sub-groups.
audit_app.command("login")(login_cmd)
audit_app.command("logout")(logout_cmd)
audit_app.add_typer(keys_app, name="keys", help="Audit API key lifecycle (operator)")
audit_app.add_typer(traces_app, name="traces", help="Trace queries (read-only)")

__all__ = ["audit_app"]

"""campus.audit commands (#54).

The audit service is a separate, user-blind deployment. Its versioned
API (/audit/v1) authenticates with its own API keys (`audit_v1_...`,
Bearer) rather than OAuth user tokens; the service's web UI has a
separate browser gate (campus#929 superadmins, campus#916
development-only key sign-in) that issues no CLI credentials. The
command group maps the API's scope model onto two capabilities: key
management (apikeys:write; campus audit keys) and trace reading
(traces:read; campus audit traces), plus login/logout and the offline
status view over the stored key — the CLI's only non-OAuth credential.
"""

import typer

from campus_cli.audit.keys import keys_app
from campus_cli.audit.login import login_cmd, logout_cmd, status_cmd
from campus_cli.audit.traces import traces_app

audit_app = typer.Typer(help="Campus Audit service commands (API-key auth)")

# login/logout/status attach directly; keys and traces are sub-groups.
audit_app.command("login")(login_cmd)
audit_app.command("logout")(logout_cmd)
audit_app.command("status")(status_cmd)
audit_app.add_typer(keys_app, name="keys", help="Audit API key lifecycle (operator)")
audit_app.add_typer(traces_app, name="traces", help="Trace queries (read-only)")

__all__ = ["audit_app"]

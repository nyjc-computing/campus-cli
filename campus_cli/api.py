"""Campus API client wrapper for campus-cli."""

import os

from campus_cli.config import config

# The SDK resolves service base URLs lazily from the environment and
# ships no built-in deployment topology (campus-common #52): unconfigured
# services raise ValueError at first property access. The CLI defaults to
# the dev deployment, so bridge the SDK's env resolution here — without
# overriding anything the user (or the fleet) set explicitly.
DEV_SDK_API_URL = "https://campusapi-development.up.railway.app"

# The CLI's own auth layer reads CAMPUS_AUTH_URL / config with the
# /auth/v1 suffix (it appends /oauth/... paths itself); the SDK wants the
# bare origin and appends service paths of its own.
AUTH_V1_SUFFIX = "/auth/v1"


def _sdk_auth_origin() -> str:
    """The bare auth origin the SDK's env resolution expects."""
    auth_url = os.environ.get("CAMPUS_AUTH_URL") or config.auth_url
    origin = auth_url.rstrip("/")
    if origin.endswith(AUTH_V1_SUFFIX):
        origin = origin[: -len(AUTH_V1_SUFFIX)]
    return origin


class CampusClient:
    """
    Wrapper for Campus API client with Bearer token authentication.

    This wraps the campus_python.Campus class for use in the CLI.
    """

    def __init__(self, token: str):
        """Initialize the client with a Bearer token.

        Args:
            token: The access token for authentication.
        """
        self._token = token
        self._campus = None

    @property
    def campus(self):
        """Lazy-load the Campus client."""
        if self._campus is None:
            from campus_python import Campus
            from campus_python.tracing import DEVICE_ID_HEADER

            # Bridge the SDK's lazy env resolution (#4): inject the dev
            # defaults before construction. CAMPUS_AUTH_URL is normalized
            # to the bare origin the SDK expects — the same variable the
            # CLI's own auth layer reads with the /auth/v1 suffix, adapted
            # per consumer at this boundary; by the time a command touches
            # this property, the auth layer has already resolved what it
            # needs (get_api_client refreshes first).
            os.environ["CAMPUS_AUTH_URL"] = _sdk_auth_origin()
            os.environ.setdefault("CAMPUS_API_URL", DEV_SDK_API_URL)

            # Create Campus instance in device mode (no credentials required)
            # We'll use Bearer token authentication instead
            self._campus = Campus(timeout=30, mode="device")
            # Set Bearer authorization
            self._campus.auth.client.set_bearer_authorization(self._token)
            # Also set it for the API client
            self._campus.api.client.set_bearer_authorization(self._token)
            # Present this install's stable device id on every call
            # (#837): bearer tokens are shared per (user, client), so
            # the header is the only way server-side spans attribute to
            # this device rather than just "a device that logged in".
            device_id = config.get_device_id()
            self._campus.api.client.set_default_header(
                DEVICE_ID_HEADER, device_id
            )
            self._campus.auth.client.set_default_header(
                DEVICE_ID_HEADER, device_id
            )

        return self._campus

    @property
    def auth_clients(self):
        """Access the auth clients resource."""
        return self.campus.auth.clients

    @property
    def auth_vaults(self):
        """Access the auth vaults resource."""
        return self.campus.auth.vaults

    @property
    def auth_users(self):
        """Access the auth users resource."""
        return self.campus.auth.users

    @property
    def auth_grants(self):
        """Access the auth access-grant store resource."""
        return self.campus.auth.grants

    @property
    def api_timetables(self):
        """Access the API timetable resource."""
        return self.campus.api.timetable

    @property
    def api_assignments(self):
        """Access the API assignments resource."""
        return self.campus.api.assignments

    @property
    def api_circles(self):
        """Access the API circles resource."""
        return self.campus.api.circles

    @property
    def api_submissions(self):
        """Access the API submissions resource."""
        return self.campus.api.submissions

    @property
    def api_files(self):
        """Access the API files resource."""
        return self.campus.api.files

    @property
    def api_hostedapps(self):
        """Access the API hosted-apps resource."""
        return self.campus.api.hostedapps

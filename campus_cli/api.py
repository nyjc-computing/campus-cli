"""Campus API client wrapper for campus-cli."""


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

            # Create Campus instance in device mode (no credentials required)
            # We'll use Bearer token authentication instead
            self._campus = Campus(timeout=30, mode="device")
            # Set Bearer authorization
            self._campus.auth.client.set_bearer_authorization(self._token)
            # Also set it for the API client
            self._campus.api.client.set_bearer_authorization(self._token)

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
    def api_timetables(self):
        """Access the API timetables resource."""
        return self.campus.api.timetables

    @property
    def api_assignments(self):
        """Access the API assignments resource."""
        return self.campus.api.assignments

    @property
    def api_circles(self):
        """Access the API circles resource."""
        return self.campus.api.circles

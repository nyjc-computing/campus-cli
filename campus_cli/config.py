"""Configuration management for Campus CLI."""

import json
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""

    pass


# OAuth client ID for public CLI/device apps
# (matches campus.config.PUBLIC_OAUTH_CLIENT_ID)
# This is a public client (is_public=True) that exists in the database
# Public clients don't have a client_secret per RFC 6749 Section 2.1
PUBLIC_OAUTH_CLIENT_ID = "guest"

# Config key holding this install's stable device id (#837).
DEVICE_ID_CONFIG_KEY = "device_id"

# Config keys for named login sessions (#113): the active-session
# pointer and the index of named sessions. The index lives in
# config.json (no secrets) because neither keyring backend can
# enumerate a service's keys.
ACTIVE_SESSION_CONFIG_KEY = "active_session"
SESSIONS_CONFIG_KEY = "sessions"


# --- Deployment routing -----------------------------------------------------
#
# Campus is deployment-agnostic (campus-common #52): the environment is the
# source of truth, and one gateway origin may front every service. The CLI
# targets production by default now that prod is rolled out; a host process
# opts into development by setting ENV=development (ENV wins over CAMPUS_ENV),
# which every project repository's .env does for local/dev work.
#
# Resolution per service (mirrors campus.common.services.resolve_base_url,
# plus the CLI's config-file tier):
#   1. CAMPUS_<SERVICE>_URL          primary override
#   2. <SERVICE>_URL                 bare alias (dedicated hosts)
#   3. config file key               auth_url / audit_url (CLI-local tier)
#   4. CAMPUS_BASE_URL, then BASE_URL   gateway origin standing in for any
#      missing service URL; the service's route prefix is appended
#   5. per-deployment gateway default (+route prefix)
#
# Values for override/base variables must be bare origins
# (scheme://host[:port], no path or trailing slash) — same contract as
# campus-common; a malformed value raises ValueError naming the variable.

ENVIRONMENT_VARS = ("ENV", "CAMPUS_ENV")  # first entry wins
BASE_URL_VARS = ("CAMPUS_BASE_URL", "BASE_URL")

# Gateway origins per deployment. Prod is the suffix-less Railway fleet; the
# gateway is nyjc-campus (the clean campus.up name was globally claimed).
DEPLOYMENT_BASE_URLS = {
    "production": "https://nyjc-campus.up.railway.app",
    "development": "https://campus-development.up.railway.app",
}
DEVELOPMENT_ALIASES = ("development", "testing")

# Route prefix appended to a gateway base URL per service. auth is special:
# the CLI's own auth layer appends /oauth/... paths itself, so it needs the
# /auth/v1 prefix baked in. The api and audit clients (SDK resource roots)
# append their /api/v1, /audit/v1 prefixes, so they take the bare origin —
# which routes through the gateway unchanged and addresses a dedicated
# service host directly.
ROUTE_PREFIXES = {
    "auth": "/auth/v1",
    "api": "",
    "audit": "",
}

# Per-service overrides: primary CAMPUS_-prefixed form, then bare alias.
SERVICE_URL_VARS = {
    "auth": ("CAMPUS_AUTH_URL", "AUTH_URL"),
    "api": ("CAMPUS_API_URL", "API_URL"),
    "audit": ("CAMPUS_AUDIT_URL", "AUDIT_URL"),
}

# CLI-local config file tier (auth/audit only; api has no config key).
CONFIG_FILE_KEYS = {
    "auth": "auth_url",
    "audit": "audit_url",
}


class Config:
    """Configuration manager for Campus CLI."""

    DEFAULT_AUTO_REFRESH = True
    DEFAULT_REFRESH_THRESHOLD = 300  # 5 minutes

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize configuration.

        Args:
            config_path: Optional path to config file. If not provided,
                        uses default location.
        """
        self._config_path = config_path or self._get_default_config_path()
        self._config: dict[str, Any] = {}
        self._load()

    def _get_default_config_path(self) -> Path:
        """Get the default configuration file path based on platform."""
        home = Path.home()

        if os.name == "nt":  # Windows
            config_dir = home / "campus-cli"
        else:  # macOS, Linux, etc.
            config_dir = home / ".config" / "campus-cli"

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def _load(self) -> None:
        """Load configuration from file."""
        if not self._config_path.exists():
            # Create default config
            self._config = {
                "auto_refresh": self.DEFAULT_AUTO_REFRESH,
                "refresh_threshold": self.DEFAULT_REFRESH_THRESHOLD,
            }
            self._save()
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise ConfigError(f"Failed to load configuration: {e}") from e

    def _save(self) -> None:
        """Save configuration to file."""
        try:
            # Set restrictive permissions on the file
            fd = os.open(
                self._config_path,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except (IOError, OSError) as e:
            raise ConfigError(f"Failed to save configuration: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: The configuration key.
            default: Default value if key not found.

        Returns:
            The configuration value or default.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: The configuration key.
            value: The value to set.
        """
        self._config[key] = value
        self._save()

    @staticmethod
    def campus_env() -> str:
        """Deployment environment: ENV wins over CAMPUS_ENV; default production.

        Lowercased so ``ENV=Development`` behaves like ``development``.
        """
        for var in ENVIRONMENT_VARS:
            value = os.getenv(var)
            if value:
                return value.strip().lower()
        return "production"

    @staticmethod
    def _valid_origin(varname: str, value: str) -> str:
        """Validate ``value`` as a bare origin, naming ``varname`` on error.

        Mirrors campus.common.services: error messages name the variable
        without echoing its value, so a mis-pasted secret stays out of logs.
        """
        parse_result = urlparse(value)
        if not parse_result.scheme or not parse_result.netloc:
            raise ValueError(
                f"{varname} must be a full origin (scheme://host[:port])"
            )
        if any((
                parse_result.path,
                parse_result.params,
                parse_result.query,
                parse_result.fragment,
        )):
            raise ValueError(
                f"{varname} must be a bare origin with no path or trailing slash"
            )
        return f"{parse_result.scheme}://{parse_result.netloc}"

    @classmethod
    def _gateway_base_url(cls) -> str:
        """Gateway origin standing in for missing service URLs.

        CAMPUS_BASE_URL, then BASE_URL; falls back to the deployment's
        built-in gateway default.
        """
        for var in BASE_URL_VARS:
            value = os.getenv(var)
            if value:
                return cls._valid_origin(var, value)
        env = cls.campus_env()
        if env in DEVELOPMENT_ALIASES:
            return DEPLOYMENT_BASE_URLS["development"]
        if env in DEPLOYMENT_BASE_URLS:
            return DEPLOYMENT_BASE_URLS[env]
        raise ValueError(
            f"Invalid deployment environment {env!r} in ENV/CAMPUS_ENV; "
            "expected development or production (staging was retired — set "
            "CAMPUS_BASE_URL or a per-service URL explicitly)"
        )

    def _resolve_service_url(self, service: str) -> str:
        """Resolve a service URL with BASE_URL as the stand-in tier."""
        for var in SERVICE_URL_VARS[service]:
            value = os.getenv(var)
            if value:
                return value
        config_key = CONFIG_FILE_KEYS.get(service)
        if config_key:
            value = self.get(config_key)
            if value:
                return value
        return self._gateway_base_url() + ROUTE_PREFIXES[service]

    @property
    def auth_url(self) -> str:
        """
        Get the auth server URL (with the /auth/v1 prefix the CLI's own
        auth layer expects).

        Resolution order:
        1. CAMPUS_AUTH_URL, then AUTH_URL
        2. auth_url key in the config file
        3. CAMPUS_BASE_URL, then BASE_URL (+/auth/v1)
        4. Deployment gateway default (+/auth/v1); production unless
           ENV/CAMPUS_ENV=development
        """
        return self._resolve_service_url("auth")

    @auth_url.setter
    def auth_url(self, value: str) -> None:
        """Set the auth server URL."""
        self.set("auth_url", value)

    @property
    def api_url(self) -> str:
        """
        Get the campus.api base URL (bare origin; the SDK appends its own
        /api/v1 prefixes). Same resolution order as auth_url minus the
        config-file tier.
        """
        return self._resolve_service_url("api")

    @property
    def audit_url(self) -> str:
        """
        Get the audit service base URL (#54; bare origin — the SDK's
        AuditRoot carries the /audit/v1 prefix itself).

        Resolution order mirrors auth_url minus the config-file detail
        (audit_url key included):
        1. CAMPUS_AUDIT_URL, then AUDIT_URL
        2. audit_url key in the config file
        3. CAMPUS_BASE_URL, then BASE_URL
        4. Deployment gateway default; production unless
           ENV/CAMPUS_ENV=development
        """
        return self._resolve_service_url("audit")

    @audit_url.setter
    def audit_url(self, value: str) -> None:
        """Set the audit service base URL."""
        self.set("audit_url", value)

    @property
    def auto_refresh(self) -> bool:
        """Get whether to automatically refresh expired tokens."""
        return self.get("auto_refresh", self.DEFAULT_AUTO_REFRESH)

    @auto_refresh.setter
    def auto_refresh(self, value: bool) -> None:
        """Set whether to automatically refresh expired tokens."""
        self.set("auto_refresh", value)

    def get_device_id(self) -> str:
        """Get (or mint-and-persist) this install's stable device id (#837).

        Device = this CLI install on this machine, per the #825 design:
        minted once, persisted in the config file, and reused across
        logins — passed at login-session creation and on API calls as
        X-Campus-Device for audit attribution. Client-asserted by
        design (same trust level as the User-Agent).
        """
        device_id = self.get(DEVICE_ID_CONFIG_KEY)
        if not device_id:
            # Same uid-device-* shape the auth service mints for the
            # browser cookie lane.
            device_id = f"uid-device-{uuid.uuid4().hex[:16]}"
            self.set(DEVICE_ID_CONFIG_KEY, device_id)
        return str(device_id)

    @property
    def active_session(self) -> str | None:
        """The active login session slot (#113).

        A session name, or None for the default slot. Every command
        reads and writes credentials through whichever slot is active.
        """
        value = self.get(ACTIVE_SESSION_CONFIG_KEY)
        return value if isinstance(value, str) and value else None

    @active_session.setter
    def active_session(self, value: str | None) -> None:
        """Point the active session at a named slot (or None)."""
        self.set(ACTIVE_SESSION_CONFIG_KEY, value)

    def get_sessions(self) -> list[str]:
        """Named sessions known to this install (unordered index)."""
        names = self.get(SESSIONS_CONFIG_KEY, [])
        if not isinstance(names, list):
            return []
        return [n for n in names if isinstance(n, str) and n]

    def add_session(self, name: str) -> None:
        """Record a named session in the index (idempotent)."""
        names = self.get_sessions()
        if name not in names:
            names.append(name)
            self.set(SESSIONS_CONFIG_KEY, names)

    def remove_session(self, name: str) -> None:
        """Drop a named session from the index (no-op when unknown)."""
        names = self.get_sessions()
        if name in names:
            names.remove(name)
            self.set(SESSIONS_CONFIG_KEY, names)

    @property
    def refresh_threshold(self) -> int:
        """Get the seconds before expiry to trigger refresh."""
        return self.get("refresh_threshold", self.DEFAULT_REFRESH_THRESHOLD)

    @refresh_threshold.setter
    def refresh_threshold(self, value: int) -> None:
        """Set the seconds before expiry to trigger refresh."""
        self.set("refresh_threshold", value)


# Global config instance
config = Config()

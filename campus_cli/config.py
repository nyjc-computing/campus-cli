"""Configuration management for Campus CLI."""

import json
import os
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""

    pass


# OAuth client ID for public CLI/device apps
# (matches campus.config.PUBLIC_OAUTH_CLIENT_ID)
# This is a public client (is_public=True) that exists in the database
# Public clients don't have a client_secret per RFC 6749 Section 2.1
PUBLIC_OAUTH_CLIENT_ID = "guest"


class Config:
    """Configuration manager for Campus CLI."""

    DEFAULT_AUTH_URL = "https://campusauth-development.up.railway.app/auth/v1"
    # Unlike campus_python's staging/production defaults, these carry the
    # /auth/v1 prefix because the CLI appends /oauth/... paths itself
    STAGING_AUTH_URL = "https://auth.campus.nyjc.dev/auth/v1"
    PRODUCTION_AUTH_URL = "https://auth.campus.nyjc.app/auth/v1"
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

    @property
    def auth_url(self) -> str:
        """
        Get the auth server URL.

        Resolution order (mirrors campus_python's base URL resolution):
        1. CAMPUS_AUTH_URL environment variable
        2. auth_url key in the config file
        3. ENV/CAMPUS_ENV environment variable (ENV wins) mapped to the
           deployment environment's auth service URL
        4. Built-in development default
        """
        env_auth_url = os.getenv("CAMPUS_AUTH_URL")
        if env_auth_url:
            return env_auth_url
        config_auth_url = self.get("auth_url")
        if config_auth_url:
            return config_auth_url
        return self._env_auth_url()

    @staticmethod
    def _env_auth_url() -> str:
        """Resolve the auth URL from the ENV/CAMPUS_ENV deployment environment."""
        campus_env = os.environ.get("ENV", os.environ.get("CAMPUS_ENV", "development"))
        match campus_env:
            case "development" | "testing":
                return Config.DEFAULT_AUTH_URL
            case "staging":
                return Config.STAGING_AUTH_URL
            case "production":
                return Config.PRODUCTION_AUTH_URL
            case _:
                raise ValueError(
                    f"Invalid deployment environment {campus_env!r} in "
                    "ENV/CAMPUS_ENV; expected development, staging, or "
                    "production (or set CAMPUS_AUTH_URL explicitly)"
                )

    @auth_url.setter
    def auth_url(self, value: str) -> None:
        """Set the auth server URL."""
        self.set("auth_url", value)

    @property
    def auto_refresh(self) -> bool:
        """Get whether to automatically refresh expired tokens."""
        return self.get("auto_refresh", self.DEFAULT_AUTO_REFRESH)

    @auto_refresh.setter
    def auto_refresh(self, value: bool) -> None:
        """Set whether to automatically refresh expired tokens."""
        self.set("auto_refresh", value)

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

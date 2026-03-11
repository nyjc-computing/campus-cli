"""Configuration management for Campus CLI."""

import json
import os
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""

    pass


# OAuth client ID for public CLI/device apps (matches campus.config.PUBLIC_OAUTH_CLIENT_ID)
# This is a special public client type that doesn't require database entry
PUBLIC_OAUTH_CLIENT_ID = "guest"


class Config:
    """Configuration manager for Campus CLI."""

    DEFAULT_API_ENDPOINT = "https://api.campus.nyc"
    DEFAULT_AUTH_URL = "https://campusauth-development.up.railway.app/auth/v1"
    DEFAULT_AUTO_REFRESH = True
    DEFAULT_REFRESH_THRESHOLD = 300  # 5 minutes

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize configuration.

        Args:
            config_path: Optional path to config file. If not provided, uses default location.
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
                "api_endpoint": self.DEFAULT_API_ENDPOINT,
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
            fd = os.open(self._config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
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
    def api_endpoint(self) -> str:
        """Get the API endpoint URL."""
        return self.get("api_endpoint", self.DEFAULT_API_ENDPOINT)

    @api_endpoint.setter
    def api_endpoint(self, value: str) -> None:
        """Set the API endpoint URL."""
        self.set("api_endpoint", value)

    @property
    def auth_url(self) -> str:
        """Get the auth server URL (from env, config, or default)."""
        # Check environment variable first
        env_auth_url = os.getenv("CAMPUS_AUTH_URL")
        if env_auth_url:
            return env_auth_url
        # Fall back to config file, then default
        return self.get("auth_url", self.DEFAULT_AUTH_URL)

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

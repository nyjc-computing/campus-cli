"""Configuration management for Campus CLI."""

import json
import os
from pathlib import Path
from typing import Any, Optional


class ConfigError(Exception):
    """Exception raised for configuration-related errors."""

    pass


class Config:
    """Configuration manager for Campus CLI."""

    DEFAULT_API_ENDPOINT = "https://api.campus.nyc"

    def __init__(self, config_path: Optional[Path] = None) -> None:
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
            with open(self._config_path, "w", encoding="utf-8") as f:
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


# Global config instance
config = Config()

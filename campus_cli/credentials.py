"""Credential storage abstraction using keyring with fallback to file."""

import json
import os
from pathlib import Path
from typing import Optional

import keyring


class CredentialError(Exception):
    """Exception raised for credential-related errors."""

    pass


class CredentialStorage:
    """Abstract credential storage with keyring backend and file fallback."""

    SERVICE_NAME = "campus-cli"
    USERNAME = "user"

    def __init__(self) -> None:
        """Initialize credential storage."""
        self._use_fallback = False
        self._fallback_path = self._get_fallback_path()

    def _get_fallback_path(self) -> Path:
        """Get the fallback credential file path based on platform."""
        home = Path.home()

        if os.name == "nt":  # Windows
            config_dir = home / "campus-cli"
        else:  # macOS, Linux, etc.
            config_dir = home / ".config" / "campus-cli"

        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "credentials.json"

    def _try_keyring(self) -> bool:
        """Try using keyring backend. Returns True if successful."""
        try:
            keyring.get_keyring()
            return True
        except Exception:
            return False

    def _read_fallback_file(self) -> dict:
        """Read credentials from fallback file."""
        if not self._fallback_path.exists():
            return {}

        try:
            with open(self._fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise CredentialError(f"Failed to read credentials file: {e}") from e

    def _write_fallback_file(self, data: dict) -> None:
        """Write credentials to fallback file."""
        try:
            # Set restrictive permissions on the file
            fd = os.open(self._fallback_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except (IOError, OSError) as e:
            raise CredentialError(f"Failed to write credentials file: {e}") from e

    def get_password(self, key: str) -> Optional[str]:
        """
        Retrieve a password/credential by key.

        Args:
            key: The credential key to retrieve.

        Returns:
            The credential value or None if not found.
        """
        # Try keyring first
        if self._try_keyring():
            try:
                value = keyring.get_password(self.SERVICE_NAME, key)
                if value is not None:
                    return value
            except Exception:
                pass

        # Fall back to file storage
        data = self._read_fallback_file()
        return data.get(key)

    def set_password(self, key: str, value: str) -> None:
        """
        Store a password/credential by key.

        Args:
            key: The credential key to store.
            value: The credential value to store.
        """
        # Try keyring first
        if self._try_keyring():
            try:
                keyring.set_password(self.SERVICE_NAME, key, value)
                return
            except Exception:
                pass  # Fall back to file storage

        # Fall back to file storage
        data = self._read_fallback_file()
        data[key] = value
        self._write_fallback_file(data)

    def delete_password(self, key: str) -> None:
        """
        Delete a password/credential by key.

        Args:
            key: The credential key to delete.

        Raises:
            CredentialError: If the credential doesn't exist or deletion fails.
        """
        # Try keyring first
        if self._try_keyring():
            try:
                keyring.delete_password(self.SERVICE_NAME, key)
                return
            except Exception:
                pass  # Fall back to file storage

        # Fall back to file storage
        data = self._read_fallback_file()
        if key not in data:
            raise CredentialError(f"Credential not found: {key}")

        del data[key]
        self._write_fallback_file(data)

    def get_token(self) -> Optional[str]:
        """
        Get the stored OAuth access token.

        Returns:
            The access token or None if not found.
        """
        return self.get_password("access_token")

    def set_token(self, token: str) -> None:
        """
        Store the OAuth access token.

        Args:
            token: The access token to store.
        """
        self.set_password("access_token", token)

    def delete_token(self) -> None:
        """Delete the stored OAuth access token."""
        self.delete_password("access_token")

    def get_refresh_token(self) -> Optional[str]:
        """
        Get the stored OAuth refresh token.

        Returns:
            The refresh token or None if not found.
        """
        return self.get_password("refresh_token")

    def set_refresh_token(self, token: str) -> None:
        """
        Store the OAuth refresh token.

        Args:
            token: The refresh token to store.
        """
        self.set_password("refresh_token", token)

    def delete_refresh_token(self) -> None:
        """Delete the stored OAuth refresh token."""
        self.delete_password("refresh_token")


# Global credential storage instance
credentials = CredentialStorage()

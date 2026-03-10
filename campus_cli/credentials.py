"""Credential storage abstraction using keyring with fallback to file."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import keyring


class CredentialError(Exception):
    """Exception raised for credential-related errors."""

    pass


class CredentialStorage:
    """Abstract credential storage with keyring backend and file fallback."""

    SERVICE_NAME = "campus-cli"

    def __init__(self) -> None:
        """Initialize credential storage."""
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

    def get_password(self, key: str) -> str | None:
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

    def get_token(self) -> str | None:
        """
        Get the stored OAuth access token.

        Returns:
            The access token or None if not found.
        """
        return self.get_password("access_token")

    def set_token(self, token: str, expires_in: int | None = None) -> None:
        """
        Store the OAuth access token.

        Args:
            token: The access token to store.
            expires_in: Optional seconds until expiry. If provided, calculates expiry timestamp.
        """
        self.set_password("access_token", token)
        if expires_in is not None:
            # Calculate expiry timestamp
            expires_at = datetime.now(timezone.utc) + datetime.timedelta(seconds=expires_in)
            self.set_token_expires_at(expires_at.isoformat())

    def delete_token(self) -> None:
        """Delete the stored OAuth access token."""
        self.delete_password("access_token")
        try:
            self.delete_password("token_expires_at")
        except CredentialError:
            pass  # May not exist

    def get_refresh_token(self) -> str | None:
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

    def get_token_expires_at(self) -> str | None:
        """
        Get the token expiry timestamp.

        Returns:
            ISO format expiry timestamp or None if not found.
        """
        return self.get_password("token_expires_at")

    def set_token_expires_at(self, expires_at: str) -> None:
        """
        Store the token expiry timestamp.

        Args:
            expires_at: ISO format timestamp string.
        """
        self.set_password("token_expires_at", expires_at)

    def is_token_expired(self, threshold_seconds: int = 0) -> bool:
        """
        Check if the stored token is expired or will expire within threshold.

        Args:
            threshold_seconds: Seconds before actual expiry to consider token expired.
                              Useful for proactive refresh.

        Returns:
            True if token is expired or will expire within threshold, False otherwise.
            Also returns True if no expiry info is stored (conservative approach).
        """
        expires_at_str = self.get_token_expires_at()
        if not expires_at_str:
            # No expiry info - assume valid if token exists
            return self.get_token() is None

        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            # Ensure we're comparing UTC times
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            return now >= (expires_at - datetime.timedelta(seconds=threshold_seconds))
        except (ValueError, TypeError):
            # Invalid expiry data - assume expired to be safe
            return True


# Global credential storage instance
credentials = CredentialStorage()

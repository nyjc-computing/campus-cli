"""Unit tests for configuration module.

These tests test individual functions and classes in the config module.
"""

import os

import pytest

from campus_cli.config import Config


@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary config file for testing."""
    config_path = tmp_path / "config.json"
    return Config(config_path=config_path)


def test_config_initialization(temp_config):
    """Test that config initializes with default values."""
    assert temp_config.get("auto_refresh") == Config.DEFAULT_AUTO_REFRESH
    assert temp_config.get("refresh_threshold") == Config.DEFAULT_REFRESH_THRESHOLD


def test_config_get_and_set(temp_config):
    """Test setting and getting config values."""
    temp_config.set("test_key", "test_value")
    result = temp_config.get("test_key")
    assert result == "test_value"


def test_config_get_returns_default_when_missing(temp_config):
    """Test that get returns default value when key doesn't exist."""
    result = temp_config.get("nonexistent_key", default="default_value")
    assert result == "default_value"


def test_config_get_returns_none_when_missing_no_default(temp_config):
    """Test that get returns None when key doesn't exist and no default."""
    result = temp_config.get("nonexistent_key")
    assert result is None


def test_config_auto_refresh_property(temp_config):
    """Test the auto_refresh property."""
    assert temp_config.auto_refresh == Config.DEFAULT_AUTO_REFRESH
    temp_config.auto_refresh = False
    assert temp_config.auto_refresh is False


def test_config_refresh_threshold_property(temp_config):
    """Test the refresh_threshold property."""
    assert temp_config.refresh_threshold == Config.DEFAULT_REFRESH_THRESHOLD
    temp_config.refresh_threshold = 600
    assert temp_config.refresh_threshold == 600


def test_config_auth_url_from_env():
    """Test that auth_url respects environment variable."""
    original_auth_url = os.environ.get("CAMPUS_AUTH_URL")
    try:
        os.environ["CAMPUS_AUTH_URL"] = "https://env-auth.example.com"
        config = Config()
        assert config.auth_url == "https://env-auth.example.com"
    finally:
        if original_auth_url:
            os.environ["CAMPUS_AUTH_URL"] = original_auth_url
        else:
            os.environ.pop("CAMPUS_AUTH_URL", None)


def test_config_auth_url_defaults_to_development(monkeypatch, tmp_path):
    """With nothing set, auth_url resolves to the built-in development default."""
    for var in ("CAMPUS_AUTH_URL", "ENV", "CAMPUS_ENV"):
        monkeypatch.delenv(var, raising=False)
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == Config.DEFAULT_AUTH_URL


def test_config_auth_url_follows_env(monkeypatch, tmp_path):
    """Each ENV value maps to its deployment environment's auth URL."""
    expected = {
        "development": Config.DEFAULT_AUTH_URL,
        "testing": Config.DEFAULT_AUTH_URL,
        "staging": Config.STAGING_AUTH_URL,
        "production": Config.PRODUCTION_AUTH_URL,
    }
    for value, url in expected.items():
        monkeypatch.setenv("ENV", value)
        config = Config(config_path=tmp_path / f"{value}.json")
        assert config.auth_url == url


def test_config_auth_url_env_wins_over_campus_env(monkeypatch, tmp_path):
    """ENV takes precedence over CAMPUS_ENV, mirroring campus_python."""
    monkeypatch.delenv("CAMPUS_AUTH_URL", raising=False)
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.setenv("CAMPUS_ENV", "production")
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == Config.STAGING_AUTH_URL


def test_config_auth_url_falls_back_to_campus_env(monkeypatch, tmp_path):
    """CAMPUS_ENV is honored when ENV is unset."""
    monkeypatch.delenv("CAMPUS_AUTH_URL", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("CAMPUS_ENV", "production")
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == Config.PRODUCTION_AUTH_URL


def test_config_auth_url_explicit_env_var_wins_over_deploy_env(monkeypatch, tmp_path):
    """CAMPUS_AUTH_URL overrides ENV/CAMPUS_ENV routing."""
    monkeypatch.setenv("CAMPUS_AUTH_URL", "https://env-auth.example.com")
    monkeypatch.setenv("ENV", "production")
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == "https://env-auth.example.com"


def test_config_auth_url_config_file_wins_over_deploy_env(monkeypatch, tmp_path):
    """The config file's auth_url overrides ENV/CAMPUS_ENV routing."""
    monkeypatch.delenv("CAMPUS_AUTH_URL", raising=False)
    monkeypatch.setenv("ENV", "production")
    config_path = tmp_path / "config.json"
    Config(config_path=config_path).set("auth_url", "https://config-auth.example.com")
    config = Config(config_path=config_path)
    assert config.auth_url == "https://config-auth.example.com"


def test_config_auth_url_invalid_env_raises(monkeypatch, tmp_path):
    """An unrecognized ENV value is an error, like campus_python."""
    monkeypatch.delenv("CAMPUS_AUTH_URL", raising=False)
    monkeypatch.setenv("ENV", "nonsense")
    config = Config(config_path=tmp_path / "config.json")
    with pytest.raises(ValueError, match="Invalid deployment environment"):
        _ = config.auth_url


def test_config_persistence(tmp_path):
    """Test that config values persist across instances."""
    config_path = tmp_path / "config.json"

    # Set value in first instance
    config1 = Config(config_path=config_path)
    config1.set("test_key", "persisted_value")

    # Check value in second instance
    config2 = Config(config_path=config_path)
    assert config2.get("test_key") == "persisted_value"


def test_config_default_path():
    """Test that Config uses default path when none provided."""
    config = Config()
    # Default path should exist
    assert config._config_path.exists()
    assert config._config_path.name == "config.json"

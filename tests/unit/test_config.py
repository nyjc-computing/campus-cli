"""Unit tests for configuration module.

These tests test individual functions and classes in the config module.
"""

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


URL_ENV_VARS = ("ENV", "CAMPUS_ENV", "CAMPUS_AUTH_URL", "AUTH_URL",
                "CAMPUS_API_URL", "API_URL", "CAMPUS_AUDIT_URL", "AUDIT_URL",
                "CAMPUS_BASE_URL", "BASE_URL")

PROD_GATEWAY = "https://nyjc-campus.up.railway.app"
DEV_GATEWAY = "https://campus-development.up.railway.app"


@pytest.fixture
def clean_url_env(monkeypatch):
    """Scrub every URL-affecting variable for deterministic resolution."""
    for var in URL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_config_auth_url_from_env(monkeypatch):
    """CAMPUS_AUTH_URL is honored verbatim."""
    monkeypatch.setenv("CAMPUS_AUTH_URL", "https://env-auth.example.com")
    config = Config()
    assert config.auth_url == "https://env-auth.example.com"


@pytest.mark.usefixtures("clean_url_env")
def test_config_urls_default_to_production(tmp_path):
    """With nothing set, every service targets the production gateway.

    The auth URL carries the /auth/v1 prefix (the CLI's auth layer appends
    /oauth/... paths itself); api and audit take the bare origin (their
    SDK resource roots append the /v1 prefixes).
    """
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == PROD_GATEWAY + "/auth/v1"
    assert config.api_url == PROD_GATEWAY
    assert config.audit_url == PROD_GATEWAY


@pytest.mark.usefixtures("clean_url_env")
def test_config_urls_follow_development_env(monkeypatch, tmp_path):
    """ENV=development falls back to the dev gateway for every service."""
    for env_value in ("ENV", "CAMPUS_ENV"):
        for value in ("development", "testing", "Development"):
            monkeypatch.setenv(env_value, value)
            config = Config(config_path=tmp_path / "config.json")
            assert config.auth_url == DEV_GATEWAY + "/auth/v1"
            assert config.api_url == DEV_GATEWAY
            monkeypatch.delenv(env_value)


@pytest.mark.usefixtures("clean_url_env")
def test_config_env_wins_over_campus_env(monkeypatch, tmp_path):
    """ENV takes precedence over CAMPUS_ENV, mirroring campus_python."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("CAMPUS_ENV", "production")
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == DEV_GATEWAY + "/auth/v1"


@pytest.mark.usefixtures("clean_url_env")
def test_config_staging_is_retired(monkeypatch, tmp_path):
    """staging environments no longer resolve; the error names the way out."""
    monkeypatch.setenv("ENV", "staging")
    config = Config(config_path=tmp_path / "config.json")
    with pytest.raises(ValueError, match="retired"):
        _ = config.auth_url


@pytest.mark.usefixtures("clean_url_env")
def test_config_invalid_env_raises(monkeypatch, tmp_path):
    """An unrecognized ENV value is an error, like campus_python."""
    monkeypatch.setenv("ENV", "nonsense")
    config = Config(config_path=tmp_path / "config.json")
    with pytest.raises(ValueError, match="Invalid deployment environment"):
        _ = config.auth_url


@pytest.mark.usefixtures("clean_url_env")
def test_config_service_vars_win_over_base_url(monkeypatch, tmp_path):
    """Per-service overrides beat BASE_URL and are used verbatim."""
    monkeypatch.setenv("BASE_URL", "https://gateway.example.com")
    monkeypatch.setenv("CAMPUS_AUTH_URL", "https://auth.example.com/oauth")
    monkeypatch.setenv("API_URL", "https://api.example.com")
    monkeypatch.setenv("AUDIT_URL", "https://audit.example.com")
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == "https://auth.example.com/oauth"
    assert config.api_url == "https://api.example.com"
    assert config.audit_url == "https://audit.example.com"


@pytest.mark.usefixtures("clean_url_env")
def test_config_base_url_stand_in(monkeypatch, tmp_path):
    """BASE_URL fronts every service; auth gets the /auth/v1 prefix."""
    monkeypatch.setenv("BASE_URL", "https://gateway.example.com")
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == "https://gateway.example.com/auth/v1"
    assert config.api_url == "https://gateway.example.com"
    assert config.audit_url == "https://gateway.example.com"


@pytest.mark.usefixtures("clean_url_env")
def test_config_campus_base_url_wins_over_bare_alias(monkeypatch, tmp_path):
    """CAMPUS_BASE_URL is the primary form of the gateway stand-in."""
    monkeypatch.setenv("CAMPUS_BASE_URL", "https://campus-gw.example.com")
    monkeypatch.setenv("BASE_URL", "https://gw.example.com")
    config = Config(config_path=tmp_path / "config.json")
    assert config.auth_url == "https://campus-gw.example.com/auth/v1"


@pytest.mark.usefixtures("clean_url_env")
def test_config_base_url_beats_deployment_default(monkeypatch, tmp_path):
    """A gateway origin set via BASE_URL overrides the built-in default."""
    monkeypatch.setenv("BASE_URL", "https://gateway.example.com")
    config = Config(config_path=tmp_path / "config.json")
    assert config.api_url == "https://gateway.example.com"


@pytest.mark.usefixtures("clean_url_env")
def test_config_file_key_beats_base_url(monkeypatch, tmp_path):
    """The config file's auth_url overrides the BASE_URL stand-in."""
    monkeypatch.setenv("BASE_URL", "https://gateway.example.com")
    config_path = tmp_path / "config.json"
    Config(config_path=config_path).set("auth_url", "https://config-auth.example.com")
    config = Config(config_path=config_path)
    assert config.auth_url == "https://config-auth.example.com"


@pytest.mark.parametrize("bad_value", [
    "gateway.example.com",                # no scheme
    "https://gateway.example.com/path",   # path
    "https://gateway.example.com/",       # trailing slash
])
@pytest.mark.usefixtures("clean_url_env")
def test_config_malformed_base_url_raises(monkeypatch, tmp_path, bad_value):
    """A non-bare-origin BASE_URL raises ValueError naming the variable."""
    monkeypatch.setenv("BASE_URL", bad_value)
    config = Config(config_path=tmp_path / "config.json")
    with pytest.raises(ValueError, match="BASE_URL"):
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

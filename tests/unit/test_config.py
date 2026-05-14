"""Unit tests for configuration module.

These tests test individual functions and classes in the config module.
"""

import pytest

from campus_cli.utils.config import get_config_path, get_config_value, set_config_value


@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary config file for testing."""
    import os

    # Temporarily override config path
    original_path = os.environ.get("CAMPUS_CONFIG_PATH")
    os.environ["CAMPUS_CONFIG_PATH"] = str(tmp_path / "config.toml")

    yield tmp_path / "config.toml"

    # Restore original path
    if original_path:
        os.environ["CAMPUS_CONFIG_PATH"] = original_path
    else:
        os.environ.pop("CAMPUS_CONFIG_PATH", None)


def test_get_config_path(temp_config):
    """Test that get_config_path returns expected path."""
    config_path = get_config_path()
    assert config_path == temp_config


def test_set_and_get_config_value(temp_config):
    """Test setting and getting config values."""
    set_config_value("test_section", "test_key", "test_value")
    result = get_config_value("test_section", "test_key")
    assert result == "test_value"


def test_get_config_value_returns_default_when_missing(temp_config):
    """Test that get_config_value returns default value when key doesn't exist."""
    result = get_config_value("nonexistent_section", "nonexistent_key", default="default_value")
    assert result == "default_value"


def test_get_config_value_returns_none_when_missing_no_default(temp_config):
    """Test that get_config_value returns None when key doesn't exist and no default."""
    result = get_config_value("nonexistent_section", "nonexistent_key")
    assert result is None

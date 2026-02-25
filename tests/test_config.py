"""Test configuration management."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def temp_config_file(tmp_path: Path):
    """Create a temporary config file."""
    config_path = tmp_path / "config.json"
    return config_path


def test_config_creates_default_file(temp_config_file):
    """Test that config creates a default file if none exists."""
    from campus_cli.config import Config

    config = Config(config_path=temp_config_file)

    assert temp_config_file.exists()
    assert config.get("api_endpoint") == "https://api.campus.nyc"


def test_config_loads_existing_file(temp_config_file):
    """Test that config loads existing values."""
    from campus_cli.config import Config

    # Write a pre-existing config
    with open(temp_config_file, "w") as f:
        json.dump({"api_endpoint": "https://custom.api.com", "custom_key": "value"}, f)

    config = Config(config_path=temp_config_file)

    assert config.api_endpoint == "https://custom.api.com"
    assert config.get("custom_key") == "value"


def test_config_set_and_persist(temp_config_file):
    """Test that config changes persist to file."""
    from campus_cli.config import Config

    config = Config(config_path=temp_config_file)
    config.set("test_key", "test_value")

    # Verify it persisted
    with open(temp_config_file) as f:
        data = json.load(f)

    assert data["test_key"] == "test_value"


def test_config_api_endpoint_property(temp_config_file):
    """Test the api_endpoint property accessor."""
    from campus_cli.config import Config

    config = Config(config_path=temp_config_file)

    assert config.api_endpoint == "https://api.campus.nyc"

    config.api_endpoint = "https://new.api.com"
    assert config.api_endpoint == "https://new.api.com"


def test_config_get_with_default(temp_config_file):
    """Test get() returns default for missing keys."""
    from campus_cli.config import Config

    config = Config(config_path=temp_config_file)

    assert config.get("missing_key") is None
    assert config.get("missing_key", "default") == "default"

"""Unit tests for grant output formatting and option validation (#50)."""

import pytest
import typer
from typer.testing import CliRunner

from campus_cli.auth.grants import (
    _format_access,
    _format_grant,
    _validate_level_bits,
)

runner = CliRunner()


def _row(**overrides):
    fields = {
        "id": "uid-grant-10131fe6",
        "grantee_type": "user",
        "grantee_id": "user@example.com",
        "resource_type": "users",
        "resource_id": "",
        "bits": None,
        "level": "write",
        "created_at": "2026-10-10T15:10:00+00:00",
    }
    fields.update(overrides)
    return fields


class TestFormatAccess:
    """_format_access renders levels and vault bitflags."""

    def test_level_row(self):
        assert _format_access(_row()) == "users:write"

    def test_vault_row_names_label_and_bits(self):
        row = _row(
            resource_type="vault",
            resource_id="email",
            level=None,
            bits=3,
        )
        assert _format_access(row) == "vault email: READ, CREATE"

    def test_zero_bits_render_as_zero(self):
        row = _row(resource_type="vault", resource_id="x", level=None, bits=0)
        assert _format_access(row) == "vault x: 0"

    def test_check_shape_without_id(self):
        row = {"resource_type": "users", "resource_id": "", "level": "read"}
        assert _format_access(row) == "users:read"


class TestFormatGrant:
    """_format_grant projects the row into display fields."""

    def test_projects_grantee_and_access(self):
        result = _format_grant(_row())
        assert result["id"] == "uid-grant-10131fe6"
        assert result["grantee"] == "user: user@example.com"
        assert result["access"] == "users:write"
        assert result["created_at"] == "2026-10-10T15:10:00+00:00"


class TestValidateLevelBits:
    """Exactly one of --level / --bits must be provided."""

    def test_neither_exits(self):
        with pytest.raises(typer.Exit):
            _validate_level_bits(None, None)

    def test_both_exit(self):
        with pytest.raises(typer.Exit):
            _validate_level_bits("write", 1)

    def test_level_alone_passes(self):
        _validate_level_bits("write", None)

    def test_bits_alone_passes(self):
        _validate_level_bits(None, 3)

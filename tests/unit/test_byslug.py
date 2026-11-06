"""Unit tests for file/hosted-app by-slug commands (#4 Phase B)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from campus_cli.cli import app

runner = CliRunner()


def _record(slug="probe", name=None, content_type="text/plain", size=13):
    return {
        "slug": slug,
        "name": name,
        "content_type": content_type,
        "content_size": size,
    }


# --- campus file ----------------------------------------------------------

def test_file_list_prefix_and_json():
    with patch("campus_cli.resources.files.get_api_client") as mock_get:
        api = MagicMock()
        api.api_files.list.return_value = [_record()]
        mock_get.return_value = api
        result = runner.invoke(
            app, ["file", "list", "--prefix", "probe", "--json"]
        )
    assert result.exit_code == 0, result.stdout
    assert api.api_files.list.call_args.kwargs == {"prefix": "probe"}
    assert json.loads(result.stdout)[0]["slug"] == "probe"


def test_file_get_meta_detail_and_json():
    with patch("campus_cli.resources.files.get_api_client") as mock_get:
        api = MagicMock()
        api.api_files.get_meta.return_value = _record(name="Probe file")
        mock_get.return_value = api
        result = runner.invoke(app, ["file", "get-meta", "--slug", "probe"])
        assert result.exit_code == 0, result.stdout
        assert "Probe file" in result.stdout
        result = runner.invoke(
            app, ["file", "get-meta", "--slug", "probe", "--json"]
        )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["content_type"] == "text/plain"


def test_file_get_content_to_output(tmp_path):
    target = tmp_path / "out.bin"
    with patch("campus_cli.resources.files.get_api_client") as mock_get:
        api = MagicMock()
        api.api_files.get_content.return_value = b"probe-content"
        mock_get.return_value = api
        result = runner.invoke(
            app, ["file", "get-content", "--slug", "probe",
                  "--output", str(target)]
        )
    assert result.exit_code == 0, result.stdout
    assert target.read_bytes() == b"probe-content"


def test_file_put_roundtrip_args(tmp_path):
    src = tmp_path / "in.txt"
    src.write_bytes(b"upload-me")
    with patch("campus_cli.resources.files.get_api_client") as mock_get:
        api = MagicMock()
        api.api_files.put_by_slug.return_value = _record()
        mock_get.return_value = api
        result = runner.invoke(app, [
            "file", "put", "--slug", "probe", "--file", str(src),
            "--content-type", "text/plain", "--name", "Probe file",
        ])
    assert result.exit_code == 0, result.stdout
    api.api_files.put_by_slug.assert_called_once_with(
        "probe", b"upload-me",
        content_type="text/plain", name="Probe file",
    )


def test_file_put_dry_run_never_reads_or_calls(tmp_path):
    src = tmp_path / "in.txt"
    src.write_bytes(b"upload-me")
    with patch("campus_cli.resources.files.get_api_client") as mock_get:
        result = runner.invoke(app, [
            "file", "put", "--slug", "probe", "--file", str(src),
            "--dry-run",
        ])
        mock_get.assert_not_called()
    assert result.exit_code == 0, result.stdout
    assert "put_by_slug(" in result.stdout
    assert "<9 bytes>" in result.stdout


def test_file_delete_confirm_gate():
    with patch("campus_cli.resources.files.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(app, ["file", "delete", "--slug", "probe"])
        assert result.exit_code == 1
        api.api_files.delete_by_slug.assert_not_called()
        result = runner.invoke(
            app, ["file", "delete", "--slug", "probe", "-y"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_files.delete_by_slug.assert_called_once_with("probe")


# --- campus app -----------------------------------------------------------

def test_app_list_and_put(tmp_path):
    src = tmp_path / "app.html"
    src.write_bytes(b"<html>hi</html>")
    with patch("campus_cli.resources.hostedapps.get_api_client") as mock_get:
        api = MagicMock()
        api.api_hostedapps.list.return_value = [_record(
            slug="quiz-app", content_type="text/html"
        )]
        api.api_hostedapps.put_by_slug.return_value = _record(
            slug="quiz-app", content_type="text/html"
        )
        mock_get.return_value = api
        result = runner.invoke(app, ["app", "list", "--json"])
        assert result.exit_code == 0, result.stdout
        assert json.loads(result.stdout)[0]["slug"] == "quiz-app"
        result = runner.invoke(app, [
            "app", "put", "--slug", "quiz-app", "--file", str(src),
        ])
        assert result.exit_code == 0, result.stdout
        api.api_hostedapps.put_by_slug.assert_called_once_with(
            "quiz-app", b"<html>hi</html>", content_type=None
        )


def test_app_get_content_stdout():
    with patch("campus_cli.resources.hostedapps.get_api_client") as mock_get:
        api = MagicMock()
        api.api_hostedapps.get_content.return_value = b"<html>hi</html>"
        mock_get.return_value = api
        result = runner.invoke(app, ["app", "get-content", "--slug", "quiz-app"])
    assert result.exit_code == 0, result.stdout
    assert "<html>hi</html>" in result.stdout


def test_app_delete_confirm_gate():
    with patch("campus_cli.resources.hostedapps.get_api_client") as mock_get:
        api = MagicMock()
        mock_get.return_value = api
        result = runner.invoke(app, ["app", "delete", "--slug", "quiz-app"])
        assert result.exit_code == 1
        api.api_hostedapps.delete_by_slug.assert_not_called()
        result = runner.invoke(
            app, ["app", "delete", "--slug", "quiz-app", "-y"]
        )
        assert result.exit_code == 0, result.stdout
        api.api_hostedapps.delete_by_slug.assert_called_once_with("quiz-app")

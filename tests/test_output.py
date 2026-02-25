"""Test output formatting utilities."""

from io import StringIO

from rich.console import Console

from campus_cli.utils import output


def test_print_success(monkeypatch):
    """Test print_success outputs correct format."""
    test_console = Console(file=StringIO(), force_terminal=True)
    monkeypatch.setattr(output, "console", test_console)

    output.print_success("Test message")

    result = test_console.file.getvalue()
    assert "Test message" in result


def test_print_table(monkeypatch):
    """Test print_table formats data correctly."""
    test_console = Console(file=StringIO(), force_terminal=True)
    monkeypatch.setattr(output, "console", test_console)

    output.print_table(
        headers=["Name", "Value"],
        rows=[["row1_col1", "row1_col2"], ["row2_col1", "row2_col2"]],
    )

    result = test_console.file.getvalue()
    assert "Name" in result
    assert "Value" in result
    assert "row1_col1" in result
    assert "row2_col2" in result


def test_print_json(monkeypatch):
    """Test print_json outputs valid JSON."""
    test_console = Console(file=StringIO(), force_terminal=True)
    monkeypatch.setattr(output, "console", test_console)

    test_data = {"key": "value", "nested": {"a": 1}}
    output.print_json(test_data)

    result = test_console.file.getvalue()
    assert '"key"' in result
    assert '"value"' in result
    assert '"nested"' in result

import pytest

pytest.importorskip("typer")
pytest.importorskip("jsonschema")

from src.cli import app
from typer.testing import CliRunner


def test_validate_data_command():
    runner = CliRunner()
    result = runner.invoke(app, ["validate-data"])
    assert result.exit_code == 0
    assert "Validation passed" in result.stdout

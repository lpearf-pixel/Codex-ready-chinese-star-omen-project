import json

import pytest

pytest.importorskip("typer")
from typer.testing import CliRunner

from src.cli import app


def test_validate_contract_commands_pass():
    runner = CliRunner()
    for command in ["validate-upstream-contract", "validate-payload-contract", "validate-consumer-contract"]:
        result = runner.invoke(app, [command])
        assert result.exit_code == 0, result.stdout
        body = json.loads(result.stdout)
        assert body["ok"] is True

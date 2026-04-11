from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass


@dataclass
class Result:
    exit_code: int
    stdout: str


class CliRunner:
    def invoke(self, app, args):
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                cmd = args[0]
                fn = app.commands[cmd]
                fn()
            return Result(exit_code=0, stdout=f.getvalue())
        except Exception:
            return Result(exit_code=1, stdout=f.getvalue())

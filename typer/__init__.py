from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class BadParameter(ValueError):
    pass


def echo(message: str) -> None:
    print(message)


@dataclass
class _Command:
    name: str
    fn: Callable[..., Any]


class Typer:
    def __init__(self, help: str | None = None):
        self.help = help
        self.commands: dict[str, Callable[..., Any]] = {}

    def command(self, name: str | None = None):
        def decorator(fn: Callable[..., Any]):
            cmd_name = name or fn.__name__.replace("_", "-")
            self.commands[cmd_name] = fn
            return fn

        return decorator

    def __call__(self):
        import sys

        argv = sys.argv[1:]
        if not argv:
            return
        cmd = argv[0]
        fn = self.commands[cmd]
        kwargs = {}
        i = 1
        while i < len(argv):
            if argv[i].startswith("--"):
                key = argv[i][2:].replace("-", "_")
                if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                    kwargs[key] = argv[i + 1]
                    i += 2
                else:
                    kwargs[key] = True
                    i += 1
            else:
                i += 1
        fn(**kwargs)

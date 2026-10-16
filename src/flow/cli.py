"""Command-line interface for Flow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from flow.errors import FlowError
from flow.parser import parse
from flow.runtime import Interpreter


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flow", description="Run plain-language Flow automations.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "preview"):
        command = commands.add_parser(name, help=f"{'Execute' if name == 'run' else 'Preview'} a .flow script")
        command.add_argument("script", type=Path, help="Path to the .flow script")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = args.script.read_text(encoding="utf-8")
        program = parse(source)
        Interpreter(dry_run=args.command == "preview").run(program)
    except (OSError, FlowError) as exc:
        print(f"Flow: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


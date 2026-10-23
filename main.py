"""Smart Compression CLI: choose smart compression, restoration, or comparison."""
from __future__ import annotations

import argparse
import importlib
import sys


COMMANDS = {"smart": "smart_compress", "decompress": "smart_decompress", "compare": "compare_compress"}


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Commands:
  smart       Predict one codec and save a verified compressed package.
  decompress  Restore a saved package and verify its size and SHA-256.
  compare     Measure all four codecs and report mode-specific scores.

Use %(prog)s COMMAND --help for that command's input and options.
""")
    parser.add_argument("command", choices=tuple(COMMANDS), help="Operation to run")
    # Stop parsing after the command so --help and every operation-specific
    # option are handled by the existing CLI, including its validation/errors.
    parser.add_argument("arguments", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    args = parser.parse_args(arguments)
    handler = importlib.import_module(COMMANDS[args.command])
    return handler.main(args.arguments, prog=f"{parser.prog} {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

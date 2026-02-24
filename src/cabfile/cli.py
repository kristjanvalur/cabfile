from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from .api import CabFile
from .errors import CabinetError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cabfile",
        description="Read and extract Windows CAB files (ZipFile-style CLI).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="Show archive member table.",
    )
    mode.add_argument(
        "-t",
        "--test",
        action="store_true",
        help="Test archive readability.",
    )
    mode.add_argument(
        "-e",
        "--extract",
        action="store_true",
        help="Extract archive members into target directory.",
    )
    parser.add_argument("cabinet", help="Path to cabinet file.")
    parser.add_argument(
        "target",
        nargs="?",
        help="Extraction target directory (required with --extract).",
    )
    return parser


def main(
    args: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the cabfile CLI and return a process-style exit code.

    The command shape mirrors ``python -m zipfile`` for listing, testing, and
    extraction workflows.
    """
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr

    parser = _build_parser()
    ns = parser.parse_args(args)

    if ns.extract and ns.target is None:
        parser.error("the following arguments are required with --extract: target")

    try:
        with CabFile(ns.cabinet) as cab:
            if ns.list:
                cab.printdir(file=out)
                return 0
            if ns.test:
                ok = cab.test()
                print(ok, file=out)
                return 0 if ok else 1
            for _ in cab.extract_members(ns.target):
                pass
            return 0
    except (CabinetError, OSError, IOError) as exc:
        print(f"Error: {exc}", file=err)
        return 2

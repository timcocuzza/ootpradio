"""Command-line entry point for OOTP Radio Companion."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ootp_radio.recap_parser import RecapParseError, parse_recap_file


def _print_recap(box_score: Path) -> int:
    recap = parse_recap_file(box_score)
    print(recap.subject)
    print()
    print(recap.body)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="ootp-radio",
        description="Read-only radio companion for Out of the Park Baseball.",
    )
    subparsers = parser.add_subparsers(dest="command")

    parse_recap_parser = subparsers.add_parser(
        "parse-recap",
        help="print the marked recap from one game box score",
    )
    parse_recap_parser.add_argument(
        "box_score",
        type=Path,
        help="path to a game_box_<GAME_ID>.html file",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "parse-recap":
            return _print_recap(args.box_score)
    except RecapParseError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

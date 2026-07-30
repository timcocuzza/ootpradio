"""Command-line entry point for OOTP Radio Companion."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from ootp_radio.narration import format_recap_narration
from ootp_radio.recap_parser import RecapParseError, parse_recap_file
from ootp_radio.speech import MacSaySpeaker, SpeechError


def _print_recap(box_score: Path) -> int:
    recap = parse_recap_file(box_score)
    print(recap.subject)
    print()
    print(recap.body)
    return 0


def _speak_recap(
    box_score: Path,
    *,
    voice: str | None,
    rate: int | None,
    dry_run: bool,
) -> int:
    recap = parse_recap_file(box_score)
    narration = format_recap_narration(recap)

    if dry_run:
        print(narration)
        return 0

    MacSaySpeaker(voice=voice, rate=rate).speak(narration)
    return 0


def _positive_integer(value: str) -> int:
    parsed_value = int(value)
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed_value


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

    speak_recap_parser = subparsers.add_parser(
        "speak-recap",
        help="speak the marked recap from one game box score",
    )
    speak_recap_parser.add_argument(
        "box_score",
        type=Path,
        help="path to a game_box_<GAME_ID>.html file",
    )
    speak_recap_parser.add_argument(
        "--voice",
        help="override the voice configured in macOS",
    )
    speak_recap_parser.add_argument(
        "--rate",
        type=_positive_integer,
        help="override the configured speech rate in words per minute",
    )
    speak_recap_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the final narration without speaking",
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
        if args.command == "speak-recap":
            return _speak_recap(
                args.box_score,
                voice=args.voice,
                rate=args.rate,
                dry_run=args.dry_run,
            )
    except (RecapParseError, SpeechError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

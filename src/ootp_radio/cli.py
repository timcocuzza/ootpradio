"""Command-line entry point for OOTP Radio Companion."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from ootp_radio.config import load_config
from ootp_radio.game_detector import (
    GameDetectionError,
    detect_latest_game,
    ensure_game_files_stable,
)
from ootp_radio.live_recap import prepare_latest_recap
from ootp_radio.narration import format_recap_narration
from ootp_radio.paths import SaveDirectoryError, validate_save_dir
from ootp_radio.recap_parser import RecapParseError, parse_recap_file
from ootp_radio.speech import MacSaySpeaker, SpeechError
from ootp_radio.state import StateError
from ootp_radio.watcher import RecapWatcher


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

    return _deliver_narration(
        narration,
        voice=voice,
        rate=rate,
        dry_run=dry_run,
    )


def _deliver_narration(
    narration: str,
    *,
    voice: str | None,
    rate: int | None,
    dry_run: bool,
) -> int:
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


def _positive_number(value: str) -> float:
    parsed_value = float(value)
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed_value


def _add_speech_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--voice",
        help="override the voice configured in macOS",
    )
    parser.add_argument(
        "--rate",
        type=_positive_integer,
        help="override the configured speech rate in words per minute",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the final narration without speaking",
    )


def _run_doctor(save_dir: Path) -> int:
    config = load_config(save_dir=save_dir)
    report = validate_save_dir(config.save_dir)

    for check in report.checks:
        print(check.render())

    return 0 if report.is_healthy else 1


def _print_latest_game(save_dir: Path) -> int:
    config = load_config(save_dir=save_dir)
    game_files = detect_latest_game(config.save_dir)
    ensure_game_files_stable(game_files)

    game_log = (
        game_files.game_log_path.name
        if game_files.game_log_path is not None
        else "not available"
    )
    highlight = (
        game_files.highlight_path.name
        if game_files.highlight_path is not None
        else "not available"
    )

    print(f"Game ID: {game_files.game_id}")
    print(f"Box score: {game_files.box_score_path.name}")
    print(f"Replay: {game_files.replay_path.name}")
    print(f"Game log: {game_log}")
    print(f"Highlight: {highlight}")
    return 0


def _recap_latest(
    save_dir: Path,
    *,
    voice: str | None,
    rate: int | None,
    dry_run: bool,
) -> int:
    config = load_config(save_dir=save_dir)
    prepared_recap = prepare_latest_recap(config.save_dir)
    return _deliver_narration(
        prepared_recap.narration_text,
        voice=voice,
        rate=rate,
        dry_run=dry_run,
    )


def _watch_latest(
    save_dir: Path,
    *,
    state_file: Path,
    poll_interval: float,
    play_current: bool,
    voice: str | None,
    rate: int | None,
) -> int:
    config = load_config(save_dir=save_dir)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    watcher = RecapWatcher(
        save_dir=config.save_dir,
        state_file=state_file,
        speaker=MacSaySpeaker(voice=voice, rate=rate),
        poll_interval_seconds=poll_interval,
        play_current=play_current,
    )
    try:
        watcher.run()
    except KeyboardInterrupt:
        print('INFO watcher_stopped reason="keyboard_interrupt"', file=sys.stderr)
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

    speak_recap_parser = subparsers.add_parser(
        "speak-recap",
        help="speak the marked recap from one game box score",
    )
    speak_recap_parser.add_argument(
        "box_score",
        type=Path,
        help="path to a game_box_<GAME_ID>.html file",
    )
    _add_speech_arguments(speak_recap_parser)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="validate an OOTP saved-league directory",
    )
    doctor_parser.add_argument(
        "--save-dir",
        type=Path,
        required=True,
        help="path to the selected .lg saved-league directory",
    )

    latest_game_parser = subparsers.add_parser(
        "latest-game",
        help="identify the newest played game and its matching files",
    )
    latest_game_parser.add_argument(
        "--save-dir",
        type=Path,
        required=True,
        help="path to the selected .lg saved-league directory",
    )

    recap_latest_parser = subparsers.add_parser(
        "recap-latest",
        help="speak the newest played game's official recap",
    )
    recap_latest_parser.add_argument(
        "--save-dir",
        type=Path,
        required=True,
        help="path to the selected .lg saved-league directory",
    )
    _add_speech_arguments(recap_latest_parser)

    watch_parser = subparsers.add_parser(
        "watch",
        help="watch for newly completed games and speak each recap once",
    )
    watch_parser.add_argument(
        "--save-dir",
        type=Path,
        required=True,
        help="path to the selected .lg saved-league directory",
    )
    watch_parser.add_argument(
        "--state-file",
        type=Path,
        default=Path("var") / "state.json",
        help="duplicate-prevention state path outside the OOTP save",
    )
    watch_parser.add_argument(
        "--poll-interval",
        type=_positive_number,
        default=2.0,
        help="seconds between checks (default: 2)",
    )
    watch_parser.add_argument(
        "--play-current",
        action="store_true",
        help="speak the current latest game when the watcher starts",
    )
    watch_parser.add_argument(
        "--voice",
        help="override the voice configured in macOS",
    )
    watch_parser.add_argument(
        "--rate",
        type=_positive_integer,
        help="override the configured speech rate in words per minute",
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
        if args.command == "doctor":
            return _run_doctor(args.save_dir)
        if args.command == "latest-game":
            return _print_latest_game(args.save_dir)
        if args.command == "recap-latest":
            return _recap_latest(
                args.save_dir,
                voice=args.voice,
                rate=args.rate,
                dry_run=args.dry_run,
            )
        if args.command == "watch":
            return _watch_latest(
                args.save_dir,
                state_file=args.state_file,
                poll_interval=args.poll_interval,
                play_current=args.play_current,
                voice=args.voice,
                rate=args.rate,
            )
    except (
        GameDetectionError,
        RecapParseError,
        SaveDirectoryError,
        SpeechError,
        StateError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Orchestrate preparation of the latest live OOTP recap."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from ootp_radio.box_score_parser import discover_same_slate_results
from ootp_radio.game_detector import detect_latest_game, ensure_game_files_stable
from ootp_radio.models import GameFiles, GameRecap, GameResult
from ootp_radio.narration import (
    append_around_league_narration,
    format_recap_narration,
)
from ootp_radio.paths import require_valid_save_dir
from ootp_radio.recap_parser import parse_recap_file


@dataclass(frozen=True)
class PreparedLiveRecap:
    """A stable latest game and its ready-to-speak official recap."""

    game_files: GameFiles
    recap: GameRecap
    narration_text: str
    around_league_results: tuple[GameResult, ...] = ()


def prepare_latest_recap(
    save_dir: Path | str,
    *,
    poll_interval_seconds: float = 0.25,
    include_around_league: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> PreparedLiveRecap:
    """Validate, detect, stabilize, parse, and format the latest recap."""
    save_path = Path(save_dir)
    require_valid_save_dir(save_path)
    game_files = detect_latest_game(save_path)
    prepared = prepare_game_recap(
        game_files,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    if include_around_league:
        return add_around_league(
            prepared,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )
    return prepared


def prepare_game_recap(
    game_files: GameFiles,
    *,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> PreparedLiveRecap:
    """Stabilize, parse, and format one already detected game."""
    ensure_game_files_stable(
        game_files,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    recap = parse_recap_file(game_files.box_score_path)
    narration_text = format_recap_narration(recap)

    return PreparedLiveRecap(
        game_files=game_files,
        recap=recap,
        narration_text=narration_text,
    )


def add_around_league(
    prepared: PreparedLiveRecap,
    *,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> PreparedLiveRecap:
    """Add stable same-slate results to an already prepared recap."""
    all_results = discover_same_slate_results(
        prepared.game_files,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    other_results = tuple(
        result
        for result in all_results
        if result.game_id != prepared.game_files.game_id
    )
    narration_text = append_around_league_narration(
        prepared.narration_text,
        all_results,
        played_game_id=prepared.game_files.game_id,
    )
    return replace(
        prepared,
        narration_text=narration_text,
        around_league_results=other_results,
    )

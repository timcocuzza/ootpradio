"""Orchestrate preparation of the latest live OOTP recap."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ootp_radio.game_detector import detect_latest_game, ensure_game_files_stable
from ootp_radio.models import GameFiles, GameRecap
from ootp_radio.narration import format_recap_narration
from ootp_radio.paths import require_valid_save_dir
from ootp_radio.recap_parser import parse_recap_file


@dataclass(frozen=True)
class PreparedLiveRecap:
    """A stable latest game and its ready-to-speak official recap."""

    game_files: GameFiles
    recap: GameRecap
    narration_text: str


def prepare_latest_recap(
    save_dir: Path | str,
    *,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> PreparedLiveRecap:
    """Validate, detect, stabilize, parse, and format the latest recap."""
    save_path = Path(save_dir)
    require_valid_save_dir(save_path)
    game_files = detect_latest_game(save_path)
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


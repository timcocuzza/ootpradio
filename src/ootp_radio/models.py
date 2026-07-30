"""Typed data returned by OOTP Radio parsers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameFiles:
    """Readable files associated with one played OOTP game."""

    game_id: int
    replay_path: Path
    box_score_path: Path
    game_log_path: Path | None
    highlight_path: Path | None


@dataclass(frozen=True)
class GameRecap:
    """A cleaned recap extracted from an OOTP game box score."""

    game_id: int
    subject: str
    body: str

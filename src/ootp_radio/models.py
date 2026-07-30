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
class GameResult:
    """Final score parsed from an OOTP box score."""

    game_id: int
    date: str | None
    away_team: str
    away_score: int
    home_team: str
    home_score: int
    away_team_id: int | None = None
    home_team_id: int | None = None


@dataclass(frozen=True)
class MessageReference:
    """One cleaned OOTP entity reference from a message."""

    name: str
    entity_type: str
    entity_id: str


@dataclass(frozen=True)
class NewsMessage:
    """A cleaned individual OOTP league message."""

    message_id: int
    headline: str
    body: str
    references: tuple[MessageReference, ...]
    source_path: Path
    modified_time_ns: int


@dataclass(frozen=True)
class SelectedNewsMessage:
    """A message retained by the conservative news filter."""

    message: NewsMessage
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class NewsPreview:
    """Counts and selected messages from one recent batch."""

    examined_count: int
    selected: tuple[SelectedNewsMessage, ...]

    @property
    def filtered_count(self) -> int:
        return self.examined_count - len(self.selected)


@dataclass(frozen=True)
class GameRecap:
    """A cleaned recap extracted from an OOTP game box score."""

    game_id: int
    subject: str
    body: str

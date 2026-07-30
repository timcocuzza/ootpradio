"""Typed data returned by OOTP Radio parsers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class BroadcastSegment(StrEnum):
    """One independently ordered radio-broadcast segment."""

    HIGHLIGHTS = "highlights"
    TEAM_RECAP = "team-recap"
    SCORES = "scores"
    NEWS = "news"


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
class LeagueSlate:
    """One stable batch of MLB final scores written for an OOTP date."""

    date: str
    results: tuple[GameResult, ...]
    modified_time_ns: int

    @property
    def key(self) -> str:
        """Return a date-level identity that cannot replay a partial update."""
        return f"slate:{self.date}"


@dataclass(frozen=True)
class GameDayEvent:
    """A controlled-team game whose replay and league slate are ready."""

    game_files: GameFiles
    slate: LeagueSlate

    @property
    def key(self) -> str:
        return f"game:{self.game_files.game_id}"

    @property
    def modified_time_ns(self) -> int:
        return self.slate.modified_time_ns


@dataclass(frozen=True)
class OffDayEvent:
    """A stable MLB score slate that does not contain the controlled team."""

    slate: LeagueSlate

    @property
    def key(self) -> str:
        return f"off-day:{self.slate.date}"

    @property
    def modified_time_ns(self) -> int:
        return self.slate.modified_time_ns


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
class GameHighlights:
    """Narration-friendly commentary extracted from a highlight replay."""

    game_id: int
    paragraphs: tuple[str, ...]
    source_path: Path


@dataclass(frozen=True)
class BroadcastSection:
    """Ready-to-speak chunks for one enabled broadcast segment."""

    segment: BroadcastSegment
    chunks: tuple[str, ...]


@dataclass(frozen=True)
class BroadcastIssue:
    """An enabled segment omitted because no content was available."""

    segment: BroadcastSegment
    reason: str


@dataclass(frozen=True)
class BroadcastPlan:
    """Ordered sections and omissions for one game broadcast."""

    game_id: int
    requested_order: tuple[BroadcastSegment, ...]
    effective_order: tuple[BroadcastSegment, ...]
    sections: tuple[BroadcastSection, ...]
    issues: tuple[BroadcastIssue, ...]


@dataclass(frozen=True)
class OffDayBroadcastPlan:
    """Ordered sections and omissions for one controlled-team off day."""

    date: str
    requested_order: tuple[BroadcastSegment, ...]
    effective_order: tuple[BroadcastSegment, ...]
    sections: tuple[BroadcastSection, ...]
    issues: tuple[BroadcastIssue, ...]


@dataclass(frozen=True)
class GameRecap:
    """A cleaned recap extracted from an OOTP game box score."""

    game_id: int
    subject: str
    body: str

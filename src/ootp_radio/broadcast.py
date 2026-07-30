"""Compose independently ordered radio segments for one completed game."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from ootp_radio.box_score_parser import (
    BoxScoreError,
    ScoreSlateNotReadyError,
    discover_same_slate_results,
)
from ootp_radio.game_detector import GameNotReadyError, ensure_game_files_stable
from ootp_radio.live_recap import prepare_game_recap
from ootp_radio.message_parser import (
    MessageBatchNotReadyError,
    MessageError,
    build_news_preview,
    build_news_preview_at,
)
from ootp_radio.models import (
    BroadcastIssue,
    BroadcastPlan,
    BroadcastSection,
    BroadcastSegment,
    GameFiles,
    GameResult,
    LeagueSlate,
    OffDayBroadcastPlan,
)
from ootp_radio.narration import (
    format_broadcast_score_chunks,
    format_news_headline_chunks,
    format_off_day_score_chunks,
)
from ootp_radio.recap_parser import RecapParseError
from ootp_radio.replay_strings import (
    HighlightError,
    HighlightNotReadyError,
    parse_highlight_file,
)


class BroadcastError(RuntimeError):
    """Base class for expected broadcast-composition failures."""


class BroadcastConfigurationError(BroadcastError):
    """Raised when the selected segment order is invalid."""


@dataclass
class _PreparationContext:
    same_slate_results: Sequence[GameResult] | None = None


def normalize_segment_order(
    segments: Sequence[BroadcastSegment],
) -> tuple[BroadcastSegment, ...]:
    """Validate unique selections and pin News to the final position."""
    requested = tuple(segments)
    if not requested:
        raise BroadcastConfigurationError(
            "Select at least one broadcast segment."
        )
    if len(set(requested)) != len(requested):
        raise BroadcastConfigurationError(
            "Each broadcast segment can be selected only once."
        )
    without_news = tuple(
        segment for segment in requested if segment is not BroadcastSegment.NEWS
    )
    if BroadcastSegment.NEWS not in requested:
        return without_news
    return (*without_news, BroadcastSegment.NEWS)


def _unavailable_reason(segment: BroadcastSegment) -> str:
    reasons = {
        BroadcastSegment.HIGHLIGHTS: "highlight replay is not available",
        BroadcastSegment.SCORES: "no other same-slate MLB scores were found",
        BroadcastSegment.NEWS: "no qualifying new MLB headlines were found",
    }
    return reasons.get(segment, "no narration content was available")


def _prepare_game_segment(
    game_files: GameFiles,
    *,
    team_name: str,
    segment: BroadcastSegment,
    context: _PreparationContext,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> BroadcastSection | BroadcastIssue:
    try:
        chunks: tuple[str, ...]
        if segment is BroadcastSegment.HIGHLIGHTS:
            if game_files.highlight_path is None:
                chunks = ()
            else:
                highlights = parse_highlight_file(
                    game_files.highlight_path,
                    poll_interval_seconds=poll_interval_seconds,
                    sleep=sleep,
                )
                chunks = highlights.paragraphs
        elif segment is BroadcastSegment.TEAM_RECAP:
            prepared_recap = prepare_game_recap(
                game_files,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
            )
            chunks = (prepared_recap.narration_text,)
        elif segment is BroadcastSegment.SCORES:
            context.same_slate_results = discover_same_slate_results(
                game_files,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
            )
            chunks = format_broadcast_score_chunks(
                context.same_slate_results,
                played_game_id=game_files.game_id,
            )
        else:
            preview = build_news_preview(
                game_files,
                team_name=team_name,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
                mlb_results=context.same_slate_results,
            )
            chunks = format_news_headline_chunks(preview)
    except (
        GameNotReadyError,
        HighlightNotReadyError,
        MessageBatchNotReadyError,
        ScoreSlateNotReadyError,
    ):
        raise
    except (
        BoxScoreError,
        HighlightError,
        MessageError,
        RecapParseError,
    ) as error:
        return BroadcastIssue(segment=segment, reason=str(error))

    if chunks:
        return BroadcastSection(segment=segment, chunks=chunks)
    return BroadcastIssue(
        segment=segment,
        reason=_unavailable_reason(segment),
    )


def iter_game_broadcast_parts(
    game_files: GameFiles,
    *,
    team_name: str,
    segments: Sequence[BroadcastSegment],
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[BroadcastSection | BroadcastIssue]:
    """Yield each section or omission only when playback reaches it."""
    effective_order = normalize_segment_order(segments)
    if not team_name.strip():
        raise BroadcastConfigurationError("Team name cannot be empty.")

    ensure_game_files_stable(
        game_files,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    context = _PreparationContext()
    for segment in effective_order:
        yield _prepare_game_segment(
            game_files,
            team_name=team_name,
            segment=segment,
            context=context,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )


def prepare_game_broadcast(
    game_files: GameFiles,
    *,
    team_name: str,
    segments: Sequence[BroadcastSegment],
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> BroadcastPlan:
    """Fully consume the lazy broadcast iterator for a printed preview."""
    requested_order = tuple(segments)
    effective_order = normalize_segment_order(requested_order)
    parts = tuple(
        iter_game_broadcast_parts(
            game_files,
            team_name=team_name,
            segments=requested_order,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )
    )

    return BroadcastPlan(
        game_id=game_files.game_id,
        requested_order=requested_order,
        effective_order=effective_order,
        sections=tuple(
            part for part in parts if isinstance(part, BroadcastSection)
        ),
        issues=tuple(
            part for part in parts if isinstance(part, BroadcastIssue)
        ),
    )


def _prepare_off_day_segment(
    slate: LeagueSlate,
    *,
    save_dir: Path,
    team_name: str,
    segment: BroadcastSegment,
    poll_interval_seconds: float,
    sleep: Callable[[float], None],
) -> BroadcastSection | BroadcastIssue:
    if segment in {
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.TEAM_RECAP,
    }:
        return BroadcastIssue(
            segment=segment,
            reason=f"{team_name} did not play on {slate.date}",
        )

    try:
        if segment is BroadcastSegment.SCORES:
            chunks = format_off_day_score_chunks(slate.results)
        else:
            preview = build_news_preview_at(
                save_dir,
                anchor_mtime_ns=slate.modified_time_ns,
                team_name=team_name,
                mlb_results=slate.results,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
            )
            chunks = format_news_headline_chunks(preview)
    except MessageBatchNotReadyError:
        raise
    except MessageError as error:
        return BroadcastIssue(segment=segment, reason=str(error))

    if chunks:
        return BroadcastSection(segment=segment, chunks=chunks)
    return BroadcastIssue(
        segment=segment,
        reason=_unavailable_reason(segment),
    )


def iter_off_day_broadcast_parts(
    slate: LeagueSlate,
    *,
    save_dir: Path | str,
    team_name: str,
    segments: Sequence[BroadcastSegment],
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[BroadcastSection | BroadcastIssue]:
    """Yield an off-day broadcast, omitting team-only segments."""
    effective_order = normalize_segment_order(segments)
    if not team_name.strip():
        raise BroadcastConfigurationError("Team name cannot be empty.")

    for segment in effective_order:
        yield _prepare_off_day_segment(
            slate,
            save_dir=Path(save_dir),
            team_name=team_name,
            segment=segment,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )


def prepare_off_day_broadcast(
    slate: LeagueSlate,
    *,
    save_dir: Path | str,
    team_name: str,
    segments: Sequence[BroadcastSegment],
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> OffDayBroadcastPlan:
    """Fully consume the lazy off-day iterator for a printed preview."""
    requested_order = tuple(segments)
    effective_order = normalize_segment_order(requested_order)
    parts = tuple(
        iter_off_day_broadcast_parts(
            slate,
            save_dir=save_dir,
            team_name=team_name,
            segments=requested_order,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )
    )
    return OffDayBroadcastPlan(
        date=slate.date,
        requested_order=requested_order,
        effective_order=effective_order,
        sections=tuple(
            part for part in parts if isinstance(part, BroadcastSection)
        ),
        issues=tuple(
            part for part in parts if isinstance(part, BroadcastIssue)
        ),
    )

"""Tests for reorderable, spoiler-aware broadcast composition."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ootp_radio.broadcast import (
    BroadcastConfigurationError,
    iter_game_broadcast_parts,
    iter_off_day_broadcast_parts,
    normalize_segment_order,
    prepare_game_broadcast,
    prepare_off_day_broadcast,
)
from ootp_radio.live_recap import PreparedLiveRecap
from ootp_radio.message_parser import MessageBatchNotReadyError, MessageError
from ootp_radio.models import (
    BroadcastSegment,
    GameFiles,
    GameHighlights,
    GameRecap,
    GameResult,
    LeagueSlate,
    NewsMessage,
    NewsPreview,
    SelectedNewsMessage,
)


def _game_files(*, with_highlight: bool = True) -> GameFiles:
    return GameFiles(
        game_id=42,
        replay_path=Path("replay_42.rpl"),
        box_score_path=Path("game_box_42.html"),
        game_log_path=None,
        highlight_path=(
            Path("highlight_42.rpl") if with_highlight else None
        ),
    )


def _prepared_recap(game_files: GameFiles) -> PreparedLiveRecap:
    recap = GameRecap(42, "Orioles Win", "Baltimore won the game.")
    return PreparedLiveRecap(
        game_files=game_files,
        recap=recap,
        narration_text=(
            "This is WBAL News Radio. Your Baltimore Orioles postgame report. "
            "Orioles Win.\n\nBaltimore won the game."
        ),
    )


def _news_preview() -> NewsPreview:
    message = NewsMessage(
        message_id=90,
        headline="Seattle Star Injured",
        body="This body must never be spoken.",
        references=(),
        source_path=Path("message90.txt"),
        modified_time_ns=1,
    )
    return NewsPreview(
        examined_count=2,
        selected=(SelectedNewsMessage(message, ("MLB team story",)),),
    )


def test_news_is_pinned_last_without_changing_other_relative_order() -> None:
    requested = (
        BroadcastSegment.NEWS,
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.SCORES,
        BroadcastSegment.TEAM_RECAP,
    )

    assert normalize_segment_order(requested) == (
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.SCORES,
        BroadcastSegment.TEAM_RECAP,
        BroadcastSegment.NEWS,
    )


@pytest.mark.parametrize(
    "segments",
    [(), (BroadcastSegment.HIGHLIGHTS, BroadcastSegment.HIGHLIGHTS)],
)
def test_empty_or_duplicate_segment_selection_is_rejected(segments) -> None:
    with pytest.raises(BroadcastConfigurationError):
        normalize_segment_order(segments)


def test_highlights_first_reveals_no_wbal_or_recap_before_action() -> None:
    game_files = _game_files()
    highlights = GameHighlights(
        game_id=42,
        paragraphs=("The pitch...", "The runner scores."),
        source_path=Path("highlight_42.rpl"),
    )

    with patch("ootp_radio.broadcast.ensure_game_files_stable"):
        with patch(
            "ootp_radio.broadcast.parse_highlight_file",
            return_value=highlights,
        ):
            with patch(
                "ootp_radio.broadcast.prepare_game_recap",
                return_value=_prepared_recap(game_files),
            ):
                plan = prepare_game_broadcast(
                    game_files,
                    team_name="Baltimore Orioles",
                    segments=(
                        BroadcastSegment.HIGHLIGHTS,
                        BroadcastSegment.TEAM_RECAP,
                    ),
                )

    assert [section.segment for section in plan.sections] == [
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.TEAM_RECAP,
    ]
    assert plan.sections[0].chunks == (
        "The pitch...",
        "The runner scores.",
    )
    assert "WBAL" not in " ".join(plan.sections[0].chunks)
    assert plan.sections[1].chunks[0].startswith("This is WBAL News Radio")


def test_news_uses_headlines_only_and_reuses_discovered_score_slate() -> None:
    game_files = _game_files(with_highlight=False)
    results = [
        GameResult(42, None, "Baltimore Orioles", 5, "Detroit Tigers", 4),
        GameResult(43, None, "Seattle Mariners", 3, "Texas Rangers", 2),
    ]

    with patch("ootp_radio.broadcast.ensure_game_files_stable"):
        with patch(
            "ootp_radio.broadcast.discover_same_slate_results",
            return_value=results,
        ):
            with patch(
                "ootp_radio.broadcast.build_news_preview",
                return_value=_news_preview(),
            ) as build_news:
                plan = prepare_game_broadcast(
                    game_files,
                    team_name="Baltimore Orioles",
                    segments=(
                        BroadcastSegment.NEWS,
                        BroadcastSegment.SCORES,
                    ),
                )

    assert plan.effective_order == (
        BroadcastSegment.SCORES,
        BroadcastSegment.NEWS,
    )
    assert plan.sections[0].chunks == (
        "Around the league.",
        "The Seattle Mariners defeated the Texas Rangers, 3 to 2.",
    )
    assert plan.sections[1].chunks == (
        "League news.",
        "Seattle Star Injured.",
    )
    assert "body" not in " ".join(plan.sections[1].chunks).casefold()
    assert build_news.call_args.kwargs["mlb_results"] == results


def test_missing_highlight_is_reported_without_losing_recap() -> None:
    game_files = _game_files(with_highlight=False)

    with patch("ootp_radio.broadcast.ensure_game_files_stable"):
        with patch(
            "ootp_radio.broadcast.prepare_game_recap",
            return_value=_prepared_recap(game_files),
        ):
            plan = prepare_game_broadcast(
                game_files,
                team_name="Baltimore Orioles",
                segments=(
                    BroadcastSegment.HIGHLIGHTS,
                    BroadcastSegment.TEAM_RECAP,
                ),
            )

    assert [section.segment for section in plan.sections] == [
        BroadcastSegment.TEAM_RECAP
    ]
    assert plan.issues[0].segment is BroadcastSegment.HIGHLIGHTS
    assert "not available" in plan.issues[0].reason


def test_empty_scores_and_news_are_reported_as_optional_omissions() -> None:
    game_files = _game_files(with_highlight=False)
    own_result = GameResult(
        42, None, "Baltimore Orioles", 5, "Detroit Tigers", 4
    )

    with patch("ootp_radio.broadcast.ensure_game_files_stable"):
        with patch(
            "ootp_radio.broadcast.discover_same_slate_results",
            return_value=[own_result],
        ):
            with patch(
                "ootp_radio.broadcast.build_news_preview",
                return_value=NewsPreview(examined_count=3, selected=()),
            ):
                plan = prepare_game_broadcast(
                    game_files,
                    team_name="Baltimore Orioles",
                    segments=(
                        BroadcastSegment.SCORES,
                        BroadcastSegment.NEWS,
                    ),
                )

    assert plan.sections == ()
    assert [issue.segment for issue in plan.issues] == [
        BroadcastSegment.SCORES,
        BroadcastSegment.NEWS,
    ]


def test_optional_news_failure_does_not_remove_ready_recap() -> None:
    game_files = _game_files(with_highlight=False)

    with patch("ootp_radio.broadcast.ensure_game_files_stable"):
        with patch(
            "ootp_radio.broadcast.prepare_game_recap",
            return_value=_prepared_recap(game_files),
        ):
            with patch(
                "ootp_radio.broadcast.build_news_preview",
                side_effect=MessageError("messages directory missing"),
            ):
                plan = prepare_game_broadcast(
                    game_files,
                    team_name="Baltimore Orioles",
                    segments=(
                        BroadcastSegment.TEAM_RECAP,
                        BroadcastSegment.NEWS,
                    ),
                )

    assert [section.segment for section in plan.sections] == [
        BroadcastSegment.TEAM_RECAP
    ]
    assert len(plan.issues) == 1
    assert plan.issues[0].segment is BroadcastSegment.NEWS
    assert plan.issues[0].reason == "messages directory missing"


def test_lazy_iteration_does_not_prepare_news_before_earlier_action() -> None:
    game_files = _game_files()
    highlights = GameHighlights(
        game_id=42,
        paragraphs=("The pitch...",),
        source_path=Path("highlight_42.rpl"),
    )

    with patch("ootp_radio.broadcast.ensure_game_files_stable"):
        with patch(
            "ootp_radio.broadcast.parse_highlight_file",
            return_value=highlights,
        ):
            with patch(
                "ootp_radio.broadcast.build_news_preview",
                return_value=_news_preview(),
            ) as build_news:
                parts = iter_game_broadcast_parts(
                    game_files,
                    team_name="Baltimore Orioles",
                    segments=(
                        BroadcastSegment.NEWS,
                        BroadcastSegment.HIGHLIGHTS,
                    ),
                )
                first_part = next(parts)
                build_news.assert_not_called()
                second_part = next(parts)

    assert first_part.segment is BroadcastSegment.HIGHLIGHTS
    assert second_part.segment is BroadcastSegment.NEWS
    build_news.assert_called_once()


def test_still_changing_news_is_retryable_instead_of_being_skipped() -> None:
    game_files = _game_files(with_highlight=False)

    with patch("ootp_radio.broadcast.ensure_game_files_stable"):
        with patch(
            "ootp_radio.broadcast.build_news_preview",
            side_effect=MessageBatchNotReadyError("message still changing"),
        ):
            with pytest.raises(
                MessageBatchNotReadyError, match="still changing"
            ):
                prepare_game_broadcast(
                    game_files,
                    team_name="Baltimore Orioles",
                    segments=(BroadcastSegment.NEWS,),
                )


def test_blank_team_name_is_rejected_before_parsing() -> None:
    with pytest.raises(BroadcastConfigurationError, match="cannot be empty"):
        prepare_game_broadcast(
            _game_files(),
            team_name="  ",
            segments=(BroadcastSegment.HIGHLIGHTS,),
            sleep=lambda _: None,
        )


def _off_day_slate() -> LeagueSlate:
    return LeagueSlate(
        date="08/04/2032",
        results=(
            GameResult(50, "08/04/2032", "Seattle Mariners", 3, "Texas Rangers", 2),
            GameResult(90, "08/04/2032", "Miami Marlins", 0, "New York Mets", 4),
        ),
        modified_time_ns=2_000_000_000_000,
    )


def test_off_day_omits_team_segments_and_reads_every_league_score() -> None:
    with patch(
        "ootp_radio.broadcast.build_news_preview_at",
        return_value=NewsPreview(examined_count=0, selected=()),
    ):
        plan = prepare_off_day_broadcast(
            _off_day_slate(),
            save_dir=Path("League.lg"),
            team_name="Baltimore Orioles",
            segments=(
                BroadcastSegment.HIGHLIGHTS,
                BroadcastSegment.TEAM_RECAP,
                BroadcastSegment.SCORES,
                BroadcastSegment.NEWS,
            ),
        )

    assert [section.segment for section in plan.sections] == [
        BroadcastSegment.SCORES
    ]
    assert plan.sections[0].chunks == (
        "Around the league.",
        "The Seattle Mariners defeated the Texas Rangers, 3 to 2.",
        "The New York Mets defeated the Miami Marlins, 4 to 0.",
    )
    assert [issue.segment for issue in plan.issues] == [
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.TEAM_RECAP,
        BroadcastSegment.NEWS,
    ]
    assert all("did not play" in issue.reason for issue in plan.issues[:2])


def test_off_day_news_remains_last_and_lazy() -> None:
    with patch(
        "ootp_radio.broadcast.build_news_preview_at",
        return_value=_news_preview(),
    ) as build_news:
        parts = iter_off_day_broadcast_parts(
            _off_day_slate(),
            save_dir=Path("League.lg"),
            team_name="Baltimore Orioles",
            segments=(BroadcastSegment.NEWS, BroadcastSegment.SCORES),
        )
        scores = next(parts)
        build_news.assert_not_called()
        news = next(parts)

    assert scores.segment is BroadcastSegment.SCORES
    assert news.segment is BroadcastSegment.NEWS
    assert "body" not in " ".join(news.chunks).casefold()
    build_news.assert_called_once()
    assert build_news.call_args.kwargs["anchor_mtime_ns"] == 2_000_000_000_000


def test_off_day_with_only_team_segments_is_safely_silent() -> None:
    plan = prepare_off_day_broadcast(
        _off_day_slate(),
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        segments=(
            BroadcastSegment.HIGHLIGHTS,
            BroadcastSegment.TEAM_RECAP,
        ),
    )

    assert plan.sections == ()
    assert len(plan.issues) == 2

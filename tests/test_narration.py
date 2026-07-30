"""Tests for deterministic recap narration formatting."""

from pathlib import Path

from ootp_radio.models import GameHighlights, GameRecap, GameResult
from ootp_radio.narration import (
    append_around_league_narration,
    format_around_league_narration,
    format_highlight_narration_chunks,
    format_recap_narration,
)


def test_baltimore_recap_uses_wbal_station_introduction() -> None:
    recap = GameRecap(
        game_id=1596,
        subject="Baltimore Gets 7-4 Win",
        body="The Baltimore Orioles defeated Detroit.",
    )

    narration = format_recap_narration(recap)

    assert narration.startswith(
        "This is WBAL News Radio. Your Baltimore Orioles postgame report. "
        "Baltimore Gets 7-4 Win."
    )
    assert narration.endswith(recap.body)


def test_unmapped_team_uses_generic_introduction() -> None:
    recap = GameRecap(
        game_id=2,
        subject="A 2-1 Win",
        body="The Portland Pioneers won the game.",
    )

    narration = format_recap_narration(recap)

    assert narration.startswith("Your OOTP postgame report. A 2-1 Win.")
    assert "WBAL" not in narration


def test_baltimore_aliases_still_select_wbal() -> None:
    recap = GameRecap(
        game_id=1624,
        subject="Tigers Absorb 5-4 Home Loss",
        body="Baltimore won the game. The Orioles improved to 64-44.",
    )

    narration = format_recap_narration(recap)

    assert narration.startswith(
        "This is WBAL News Radio. Your Baltimore Orioles postgame report."
    )


def test_around_league_uses_articles_and_excludes_played_game() -> None:
    results = [
        GameResult(1596, None, "Baltimore Orioles", 7, "Detroit Tigers", 4),
        GameResult(1600, None, "Seattle Mariners", 10, "Texas Rangers", 3),
    ]

    narration = format_around_league_narration(results, played_game_id=1596)

    assert narration == (
        "Now, around the league. The Seattle Mariners defeated the Texas "
        "Rangers, 10 to 3."
    )
    assert "Baltimore Orioles" not in narration


def test_no_other_results_leaves_recap_narration_unchanged() -> None:
    recap_narration = "Your postgame report."
    results = [
        GameResult(1596, None, "Baltimore Orioles", 7, "Detroit Tigers", 4)
    ]

    combined = append_around_league_narration(
        recap_narration,
        results,
        played_game_id=1596,
    )

    assert combined == recap_narration


def test_highlight_narration_keeps_intro_and_plays_in_separate_chunks() -> None:
    highlights = GameHighlights(
        game_id=1596,
        paragraphs=("First scoring play.", "Second scoring play."),
        source_path=Path("highlight_1596.rpl"),
    )

    chunks = format_highlight_narration_chunks(highlights)

    assert chunks == (
        "Now, the game highlights.",
        "First scoring play.",
        "Second scoring play.",
    )

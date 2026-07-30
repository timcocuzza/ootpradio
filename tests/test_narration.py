"""Tests for deterministic recap narration formatting."""

from ootp_radio.models import GameRecap
from ootp_radio.narration import format_recap_narration


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


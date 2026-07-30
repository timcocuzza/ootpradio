"""Command-line behavior tests."""

from pathlib import Path
from unittest.mock import patch

from ootp_radio.cli import main

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "game_1596" / "game_box_1596.html"
)


def test_speak_recap_dry_run_prints_narration_without_speaking(capsys) -> None:
    with patch("ootp_radio.cli.MacSaySpeaker.speak") as speak:
        result = main(["speak-recap", str(FIXTURE_PATH), "--dry-run"])

    output = capsys.readouterr().out
    speak.assert_not_called()
    assert result == 0
    assert output.startswith(
        "This is WBAL News Radio. Your Baltimore Orioles postgame report."
    )
    assert "DJ Layton" in output
    assert "<a href=" not in output

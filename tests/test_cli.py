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


def test_doctor_prints_expected_live_save_checks(tmp_path: Path, capsys) -> None:
    save_dir = tmp_path / "League With Spaces.lg"
    (save_dir / "replays").mkdir(parents=True)
    (save_dir / "news" / "html" / "box_scores").mkdir(parents=True)
    (save_dir / "news" / "txt" / "leagues").mkdir(parents=True)
    (save_dir / "messages").mkdir()
    (save_dir / "news" / "html" / "leagues").mkdir()

    result = main(["doctor", "--save-dir", str(save_dir)])

    output = capsys.readouterr().out
    assert result == 0
    assert "PASS: save directory exists" in output
    assert "PASS: replays directory exists" in output
    assert "PASS: box_scores directory exists" in output
    assert "PASS: messages directory exists" in output

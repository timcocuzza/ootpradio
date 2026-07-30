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


def test_latest_game_prints_matching_files(tmp_path: Path, capsys) -> None:
    save_dir = tmp_path / "League With Spaces.lg"
    (save_dir / "replays").mkdir(parents=True)
    (save_dir / "news" / "html" / "box_scores").mkdir(parents=True)
    (save_dir / "news" / "txt" / "leagues").mkdir(parents=True)
    (save_dir / "replays" / "replay_1596.rpl").write_bytes(b"replay")
    (save_dir / "replays" / "highlight_1596.rpl").write_bytes(b"highlight")
    (save_dir / "news" / "html" / "box_scores" / "game_box_1596.html").write_text(
        "box score", encoding="utf-8"
    )
    (save_dir / "news" / "txt" / "leagues" / "log_1596.txt").write_text(
        "game log", encoding="utf-8"
    )

    with patch("ootp_radio.cli.ensure_game_files_stable"):
        result = main(["latest-game", "--save-dir", str(save_dir)])

    output = capsys.readouterr().out
    assert result == 0
    assert "Game ID: 1596" in output
    assert "Box score: game_box_1596.html" in output
    assert "Replay: replay_1596.rpl" in output
    assert "Game log: log_1596.txt" in output
    assert "Highlight: highlight_1596.rpl" in output

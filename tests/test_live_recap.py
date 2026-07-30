"""Tests for the on-demand latest-recap pipeline."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ootp_radio.game_detector import GameNotReadyError
from ootp_radio.live_recap import prepare_latest_recap
from ootp_radio.paths import SaveDirectoryError

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "game_1596" / "game_box_1596.html"
)


def _create_live_save(tmp_path: Path) -> tuple[Path, Path]:
    save_dir = tmp_path / "Live League With Spaces.lg"
    (save_dir / "replays").mkdir(parents=True)
    box_scores_dir = save_dir / "news" / "html" / "box_scores"
    box_scores_dir.mkdir(parents=True)
    replay = save_dir / "replays" / "replay_1596.rpl"
    box_score = box_scores_dir / "game_box_1596.html"
    replay.write_bytes(b"replay")
    box_score.write_bytes(FIXTURE_PATH.read_bytes())
    return save_dir, box_score


def test_prepares_latest_official_recap_for_narration(tmp_path: Path) -> None:
    save_dir, _ = _create_live_save(tmp_path)
    sleeps: list[float] = []

    prepared = prepare_latest_recap(save_dir, sleep=sleeps.append)

    assert sleeps == [0.25]
    assert prepared.game_files.game_id == 1596
    assert prepared.recap.subject == "Baltimore Gets 7-4 Win"
    assert prepared.narration_text.startswith(
        "This is WBAL News Radio. Your Baltimore Orioles postgame report."
    )
    assert "DJ Layton" in prepared.narration_text


def test_invalid_save_stops_before_game_detection(tmp_path: Path) -> None:
    missing_save = tmp_path / "Missing League.lg"

    with patch("ootp_radio.live_recap.detect_latest_game") as detect:
        with pytest.raises(SaveDirectoryError, match="save directory is missing"):
            prepare_latest_recap(missing_save, sleep=lambda _: None)

    detect.assert_not_called()


def test_changing_box_score_is_not_parsed(tmp_path: Path) -> None:
    save_dir, box_score = _create_live_save(tmp_path)

    def change_box_score(_: float) -> None:
        box_score.write_text("still changing", encoding="utf-8")

    with patch("ootp_radio.live_recap.parse_recap_file") as parse:
        with pytest.raises(GameNotReadyError, match="still being written"):
            prepare_latest_recap(save_dir, sleep=change_box_score)

    parse.assert_not_called()


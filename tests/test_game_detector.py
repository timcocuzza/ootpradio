"""Tests for latest played-game detection and stability checks."""

import os
from pathlib import Path

import pytest

from ootp_radio.game_detector import (
    GameNotReadyError,
    NoReplayFilesError,
    detect_latest_game,
    ensure_game_files_stable,
)


def _create_save_dir(tmp_path: Path) -> Path:
    save_dir = tmp_path / "League With Spaces.lg"
    (save_dir / "replays").mkdir(parents=True)
    (save_dir / "news" / "html" / "box_scores").mkdir(parents=True)
    (save_dir / "news" / "txt" / "leagues").mkdir(parents=True)
    return save_dir


def _create_game_files(save_dir: Path, game_id: int) -> tuple[Path, Path]:
    replay = save_dir / "replays" / f"replay_{game_id}.rpl"
    box_score = (
        save_dir / "news" / "html" / "box_scores" / f"game_box_{game_id}.html"
    )
    replay.write_bytes(b"replay")
    box_score.write_text("box score", encoding="utf-8")
    return replay, box_score


def test_selects_replay_with_latest_modification_time(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    old_replay, _ = _create_game_files(save_dir, 10)
    new_replay, _ = _create_game_files(save_dir, 11)
    os.utime(old_replay, ns=(1_000_000_000, 1_000_000_000))
    os.utime(new_replay, ns=(2_000_000_000, 2_000_000_000))

    game_files = detect_latest_game(save_dir)

    assert game_files.game_id == 11
    assert game_files.replay_path == new_replay


def test_resolves_matching_box_log_and_highlight_files(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    replay, box_score = _create_game_files(save_dir, 42)
    game_log = save_dir / "news" / "txt" / "leagues" / "log_42.txt"
    highlight = save_dir / "replays" / "highlight_42.rpl"
    game_log.write_text("log", encoding="utf-8")
    highlight.write_bytes(b"highlight")

    game_files = detect_latest_game(save_dir)

    assert game_files.replay_path == replay
    assert game_files.box_score_path == box_score
    assert game_files.game_log_path == game_log
    assert game_files.highlight_path == highlight


def test_paths_with_spaces_work(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _create_game_files(save_dir, 7)

    game_files = detect_latest_game(save_dir)

    assert game_files.box_score_path.is_relative_to(save_dir)
    assert "League With Spaces.lg" in str(game_files.replay_path)


def test_missing_matching_box_score_reports_not_ready(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    replay = save_dir / "replays" / "replay_42.rpl"
    replay.write_bytes(b"replay")

    with pytest.raises(
        GameNotReadyError,
        match=r"latest replay is game 42, but game_box_42\.html is not ready yet",
    ):
        detect_latest_game(save_dir)


def test_unrelated_rpl_files_are_ignored(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _create_game_files(save_dir, 7)
    unrelated = save_dir / "replays" / "highlight_999.rpl"
    unrelated.write_bytes(b"newer but unrelated")
    os.utime(unrelated, ns=(9_000_000_000, 9_000_000_000))

    assert detect_latest_game(save_dir).game_id == 7


def test_non_numeric_replay_filenames_are_ignored(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _create_game_files(save_dir, 7)
    (save_dir / "replays" / "replay_final.rpl").write_bytes(b"not a game id")

    assert detect_latest_game(save_dir).game_id == 7


def test_no_numeric_replays_has_a_clear_error(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    (save_dir / "replays" / "replay_final.rpl").write_bytes(b"not a game id")

    with pytest.raises(NoReplayFilesError, match="No replay_<GAME_ID>"):
        detect_latest_game(save_dir)


def test_unchanged_required_files_are_stable(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _create_game_files(save_dir, 7)
    game_files = detect_latest_game(save_dir)
    sleeps: list[float] = []

    ensure_game_files_stable(game_files, sleep=sleeps.append)

    assert sleeps == [0.25]


def test_changing_required_file_is_not_ready(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _, box_score = _create_game_files(save_dir, 7)
    game_files = detect_latest_game(save_dir)

    def change_box_score(_: float) -> None:
        box_score.write_text("a larger box score", encoding="utf-8")

    with pytest.raises(GameNotReadyError, match="still being written by OOTP"):
        ensure_game_files_stable(game_files, sleep=change_box_score)


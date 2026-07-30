"""Smoke tests for the game-1596 regression fixture."""

from pathlib import Path


def test_game_1596_fixture_files_exist() -> None:
    fixture_dir = Path(__file__).parent / "fixtures" / "game_1596"
    expected_files = {
        "game_box_1596.html",
        "log_1596.txt",
        "highlight_1596.rpl",
        "replay_1596.rpl",
    }

    assert {path.name for path in fixture_dir.iterdir() if path.is_file()} == expected_files

"""Tests for application configuration loading."""

from pathlib import Path

from ootp_radio.config import load_config


def test_load_config_preserves_a_save_path_with_spaces(tmp_path: Path) -> None:
    save_dir = tmp_path / "My Baseball Universe.lg"

    config = load_config(save_dir=save_dir)

    assert config.save_dir == save_dir
    assert isinstance(config.save_dir, Path)


def test_load_config_keeps_explicit_team_name(tmp_path: Path) -> None:
    config = load_config(
        save_dir=tmp_path / "League.lg",
        team_name="Baltimore Orioles",
    )

    assert config.team_name == "Baltimore Orioles"

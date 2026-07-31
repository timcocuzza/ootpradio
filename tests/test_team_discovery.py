"""Tests for read-only MLB team discovery across multiple recent slates."""

import os
from pathlib import Path

import pytest

from ootp_radio.models import TeamOption
from ootp_radio.team_discovery import TeamDiscoveryError, discover_mlb_teams


def _box_html(
    *,
    game_id: int,
    away_name: str,
    away_id: int,
    home_name: str,
    home_id: int,
    league: str = "MLB",
    include_links: bool = True,
) -> str:
    links = ""
    if include_links:
        links = (
            f'<a href="../teams/team_{away_id}.html">{away_name}</a>'
            f'<a href="../teams/team_{home_id}.html">{home_name}</a>'
        )
    return f"""
    <title>{league} Box Score, {away_name} at {home_name}, 08/05/2032</title>
    <div>GAME ID: {game_id}</div>
    {links}
    <table>
      <tr><th></th><th>R</th><th>H</th><th>E</th></tr>
      <tr><td>{away_name} (50-40)</td><td>5</td><td>9</td><td>0</td></tr>
      <tr><td>{home_name} (45-45)</td><td>3</td><td>8</td><td>1</td></tr>
    </table>
    """


def _write_box(
    box_scores_dir: Path,
    *,
    game_id: int,
    modified_time_ns: int,
    **html_kwargs,
) -> Path:
    path = box_scores_dir / f"game_box_{game_id}.html"
    path.write_text(
        _box_html(game_id=game_id, **html_kwargs),
        encoding="utf-8",
    )
    os.utime(path, ns=(modified_time_ns, modified_time_ns))
    return path


def test_discovers_team_missing_from_latest_off_day_slate(tmp_path: Path) -> None:
    box_scores_dir = (
        tmp_path / "League With Spaces.lg" / "news" / "html" / "box_scores"
    )
    box_scores_dir.mkdir(parents=True)
    _write_box(
        box_scores_dir,
        game_id=10,
        modified_time_ns=100,
        away_name="Baltimore Orioles",
        away_id=3,
        home_name="Detroit Tigers",
        home_id=10,
    )
    _write_box(
        box_scores_dir,
        game_id=11,
        modified_time_ns=200,
        away_name="Seattle Mariners",
        away_id=24,
        home_name="Texas Rangers",
        home_id=28,
    )

    teams = discover_mlb_teams(tmp_path / "League With Spaces.lg")

    assert teams == (
        TeamOption(3, "Baltimore Orioles"),
        TeamOption(10, "Detroit Tigers"),
        TeamOption(24, "Seattle Mariners"),
        TeamOption(28, "Texas Rangers"),
    )


def test_newest_name_wins_when_team_id_was_renamed(tmp_path: Path) -> None:
    save_dir = tmp_path / "League.lg"
    box_scores_dir = save_dir / "news" / "html" / "box_scores"
    box_scores_dir.mkdir(parents=True)
    _write_box(
        box_scores_dir,
        game_id=10,
        modified_time_ns=100,
        away_name="Old Baltimore Club",
        away_id=3,
        home_name="Detroit Tigers",
        home_id=10,
    )
    _write_box(
        box_scores_dir,
        game_id=11,
        modified_time_ns=200,
        away_name="Baltimore Orioles",
        away_id=3,
        home_name="Detroit Tigers",
        home_id=10,
    )

    teams = discover_mlb_teams(save_dir)

    assert TeamOption(3, "Baltimore Orioles") in teams
    assert all(team.name != "Old Baltimore Club" for team in teams)


def test_minor_league_and_in_progress_boxes_do_not_break_selector(
    tmp_path: Path,
) -> None:
    save_dir = tmp_path / "League.lg"
    box_scores_dir = save_dir / "news" / "html" / "box_scores"
    box_scores_dir.mkdir(parents=True)
    _write_box(
        box_scores_dir,
        game_id=10,
        modified_time_ns=100,
        away_name="Baltimore Orioles",
        away_id=3,
        home_name="Detroit Tigers",
        home_id=10,
    )
    _write_box(
        box_scores_dir,
        game_id=11,
        modified_time_ns=200,
        away_name="Norfolk Tides",
        away_id=100,
        home_name="Durham Bulls",
        home_id=101,
        league="AAA",
    )
    changing = box_scores_dir / "game_box_12.html"
    changing.write_text("<title>MLB Box Score", encoding="utf-8")
    os.utime(changing, ns=(300, 300))

    teams = discover_mlb_teams(save_dir)

    assert teams == (
        TeamOption(3, "Baltimore Orioles"),
        TeamOption(10, "Detroit Tigers"),
    )


def test_box_scores_without_team_ids_have_clear_remedy(tmp_path: Path) -> None:
    save_dir = tmp_path / "League.lg"
    box_scores_dir = save_dir / "news" / "html" / "box_scores"
    box_scores_dir.mkdir(parents=True)
    _write_box(
        box_scores_dir,
        game_id=10,
        modified_time_ns=100,
        away_name="Baltimore Orioles",
        away_id=3,
        home_name="Detroit Tigers",
        home_id=10,
        include_links=False,
    )

    with pytest.raises(TeamDiscoveryError, match="Complete at least one MLB game"):
        discover_mlb_teams(save_dir)


def test_missing_box_score_directory_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(TeamDiscoveryError, match="does not exist"):
        discover_mlb_teams(tmp_path / "Missing.lg")


def test_nonpositive_scan_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        discover_mlb_teams(Path("unused"), max_box_scores=0)

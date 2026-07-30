"""Tests for deterministic MLB final-score parsing and slate discovery."""

import os
from pathlib import Path

import pytest

from ootp_radio.box_score_parser import (
    BoxScoreParseError,
    NotMajorLeagueBoxScoreError,
    ScoreSlateNotReadyError,
    discover_same_slate_results,
    parse_box_score_file,
    parse_box_score_html,
)
from ootp_radio.models import GameFiles, GameResult
from ootp_radio.narration import format_score_sentence

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "game_1596" / "game_box_1596.html"
)


def _box_html(
    *,
    game_id: int,
    away_team: str = "Seattle Mariners",
    away_score: int = 10,
    home_team: str = "Texas Rangers",
    home_score: int = 3,
    date: str = "08/01/2032",
    league_label: str = "MLB",
) -> str:
    return f"""
    <html>
      <head><title>{league_label} Box Score, {away_team} at {home_team}, {date}</title></head>
      <body>
        <div>GAME ID: {game_id}</div>
        <table class="data">
          <tr><th>&#160;</th><th>1</th><th><b>R</b></th><th><b>H</b></th><th><b>E</b></th></tr>
          <tr>
            <td>{away_team} (50-40)</td><td>0</td>
            <td><b>{away_score}</b></td><td>10</td><td>0</td>
          </tr>
          <tr>
            <td>{home_team} (45-45)</td><td>0</td>
            <td><b>{home_score}</b></td><td>8</td><td>1</td>
          </tr>
        </table>
        <!--RECAP_START--><!--RECAP_END-->
      </body>
    </html>
    """


def _create_slate(tmp_path: Path) -> tuple[Path, GameFiles, int]:
    save_dir = tmp_path / "League With Score Spaces.lg"
    replays_dir = save_dir / "replays"
    box_scores_dir = save_dir / "news" / "html" / "box_scores"
    replays_dir.mkdir(parents=True)
    box_scores_dir.mkdir(parents=True)
    replay = replays_dir / "replay_100.rpl"
    played_box = box_scores_dir / "game_box_100.html"
    replay.write_bytes(b"replay")
    played_box.write_text(_box_html(game_id=100), encoding="utf-8")
    anchor_ns = 2_000_000_000_000
    os.utime(replay, ns=(anchor_ns, anchor_ns))
    os.utime(played_box, ns=(anchor_ns, anchor_ns))
    return (
        save_dir,
        GameFiles(100, replay, played_box, None, None),
        anchor_ns,
    )


def test_parses_game_1596_fixture_result() -> None:
    result = parse_box_score_file(FIXTURE_PATH)

    assert result == GameResult(
        game_id=1596,
        date="08/01/2032",
        away_team="Baltimore Orioles",
        away_score=7,
        home_team="Detroit Tigers",
        home_score=4,
    )


def test_parses_simulated_box_without_a_recap() -> None:
    result = parse_box_score_html(_box_html(game_id=200), game_id=200)

    assert result.away_team == "Seattle Mariners"
    assert result.away_score == 10
    assert result.home_team == "Texas Rangers"
    assert result.home_score == 3


def test_rejects_non_mlb_box_score() -> None:
    document = _box_html(game_id=200, league_label="AAA")

    with pytest.raises(NotMajorLeagueBoxScoreError, match="not an MLB box score"):
        parse_box_score_html(document, game_id=200)


def test_missing_line_score_has_a_clear_error() -> None:
    document = (
        "<title>MLB Box Score, Seattle Mariners at Texas Rangers, 08/01/2032</title>"
        "<div>GAME ID: 200</div>"
    )

    with pytest.raises(BoxScoreParseError, match="Could not find the final R/H/E"):
        parse_box_score_html(document, game_id=200)


def test_mismatched_document_and_filename_game_ids_are_rejected() -> None:
    with pytest.raises(BoxScoreParseError, match="says game 200.*identifies game 201"):
        parse_box_score_html(_box_html(game_id=200), game_id=201)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            GameResult(1, None, "Seattle", 10, "Texas", 3),
            "The Seattle defeated the Texas, 10 to 3.",
        ),
        (
            GameResult(2, None, "Miami", 0, "Philadelphia", 12),
            "The Philadelphia defeated the Miami, 12 to 0.",
        ),
    ],
)
def test_formats_neutral_score_sentence(result: GameResult, expected: str) -> None:
    assert format_score_sentence(result) == expected


def test_discovers_noncontiguous_same_time_same_date_mlb_games(tmp_path: Path) -> None:
    save_dir, game_files, anchor_ns = _create_slate(tmp_path)
    box_scores_dir = game_files.box_score_path.parent
    candidates = {
        305: (_box_html(game_id=305), anchor_ns + 1_000_000_000),
        400: (_box_html(game_id=400, date="08/02/2032"), anchor_ns),
        500: (_box_html(game_id=500, league_label="AAA"), anchor_ns),
        999: (_box_html(game_id=999), anchor_ns + 6_000_000_000),
    }
    for game_id, (document, mtime_ns) in candidates.items():
        path = box_scores_dir / f"game_box_{game_id}.html"
        path.write_text(document, encoding="utf-8")
        os.utime(path, ns=(mtime_ns, mtime_ns))

    results = discover_same_slate_results(game_files, sleep=lambda _: None)

    assert [result.game_id for result in results] == [100, 305]
    assert all(result.date == "08/01/2032" for result in results)
    assert all(result.game_id not in {400, 500, 999} for result in results)
    assert save_dir.name == "League With Score Spaces.lg"


def test_changing_same_slate_box_score_reports_not_ready(tmp_path: Path) -> None:
    _, game_files, _ = _create_slate(tmp_path)

    def change_box_score(_: float) -> None:
        game_files.box_score_path.write_text(
            _box_html(game_id=100) + "<!-- still changing -->",
            encoding="utf-8",
        )

    with pytest.raises(ScoreSlateNotReadyError, match="still being written"):
        discover_same_slate_results(game_files, sleep=change_box_score)

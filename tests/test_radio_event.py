"""Spoiler-safety tests for game-day versus off-day classification."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ootp_radio.game_detector import NoReplayFilesError
from ootp_radio.models import GameDayEvent, GameFiles, GameResult, LeagueSlate, OffDayEvent
from ootp_radio.radio_event import (
    LatestRadioEventDetector,
    RadioEventNotReadyError,
    TeamResolutionError,
    resolve_team_id,
)


def _result(
    game_id: int,
    away_team: str,
    away_team_id: int,
    home_team: str,
    home_team_id: int,
) -> GameResult:
    return GameResult(
        game_id,
        "08/04/2032",
        away_team,
        5,
        home_team,
        3,
        away_team_id,
        home_team_id,
    )


def _slate(*results: GameResult) -> LeagueSlate:
    return LeagueSlate("08/04/2032", tuple(results), 2_000_000_000_000)


def _game(game_id: int) -> GameFiles:
    return GameFiles(
        game_id,
        Path(f"replay_{game_id}.rpl"),
        Path(f"game_box_{game_id}.html"),
        None,
        None,
    )


def test_slate_without_resolved_team_is_an_off_day() -> None:
    slate = _slate(_result(50, "Seattle Mariners", 24, "Texas Rangers", 28))
    detector = LatestRadioEventDetector(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        team_id=3,
    )

    with patch(
        "ootp_radio.radio_event.discover_latest_mlb_slate",
        return_value=slate,
    ):
        event = detector.detect()

    assert isinstance(event, OffDayEvent)
    assert event.key == "off-day:08/04/2032"


def test_team_result_waits_for_replay_instead_of_leaking_score() -> None:
    slate = _slate(_result(51, "Baltimore Orioles", 3, "Detroit Tigers", 10))
    detector = LatestRadioEventDetector(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        team_id=3,
    )

    with patch(
        "ootp_radio.radio_event.discover_latest_mlb_slate",
        return_value=slate,
    ):
        with patch(
            "ootp_radio.radio_event.detect_latest_game",
            side_effect=NoReplayFilesError("not yet"),
        ):
            with pytest.raises(RadioEventNotReadyError, match="replay is not ready"):
                detector.detect()


def test_older_replay_does_not_turn_team_game_into_off_day() -> None:
    slate = _slate(_result(51, "Baltimore Orioles", 3, "Detroit Tigers", 10))
    detector = LatestRadioEventDetector(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        team_id=3,
    )

    with patch(
        "ootp_radio.radio_event.discover_latest_mlb_slate",
        return_value=slate,
    ):
        with patch(
            "ootp_radio.radio_event.detect_latest_game",
            return_value=_game(40),
        ):
            with pytest.raises(RadioEventNotReadyError, match="earlier game"):
                detector.detect()


def test_matching_stable_replay_produces_game_day_event() -> None:
    slate = _slate(_result(51, "Baltimore Orioles", 3, "Detroit Tigers", 10))
    game_files = _game(51)
    detector = LatestRadioEventDetector(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        team_id=3,
    )

    with patch(
        "ootp_radio.radio_event.discover_latest_mlb_slate",
        return_value=slate,
    ):
        with patch(
            "ootp_radio.radio_event.detect_latest_game",
            return_value=game_files,
        ):
            with patch("ootp_radio.radio_event.ensure_game_files_stable"):
                event = detector.detect()

    assert isinstance(event, GameDayEvent)
    assert event.game_files is game_files
    assert event.key == "game:51"


def test_team_name_mismatch_errors_instead_of_declaring_false_off_day(
    tmp_path: Path,
) -> None:
    box_scores_dir = tmp_path / "League.lg" / "news" / "html" / "box_scores"
    box_scores_dir.mkdir(parents=True)
    path = box_scores_dir / "game_box_51.html"
    path.write_text(
        """
        <title>MLB Box Score, Baltimore Orioles at Detroit Tigers, 08/04/2032</title>
        <div>GAME ID: 51</div>
        <a href="../teams/team_3.html">Baltimore Orioles</a>
        <a href="../teams/team_10.html">Detroit Tigers</a>
        <table>
          <tr><th></th><th>R</th><th>H</th><th>E</th></tr>
          <tr><td>Baltimore Orioles (50-40)</td><td>5</td><td>9</td><td>0</td></tr>
          <tr><td>Detroit Tigers (45-45)</td><td>3</td><td>8</td><td>1</td></tr>
        </table>
        """,
        encoding="utf-8",
    )

    with pytest.raises(TeamResolutionError, match="complete OOTP team name"):
        resolve_team_id(
            tmp_path / "League.lg",
            team_name="Baltimore Orioels",
        )


def test_exact_team_name_resolves_case_and_extra_whitespace() -> None:
    slate = _slate(_result(51, "Baltimore Orioles", 3, "Detroit Tigers", 10))

    team_id = resolve_team_id(
        Path("unused"),
        team_name="  baltimore   ORIOLES ",
        latest_slate=slate,
    )

    assert team_id == 3

"""Command-line behavior tests."""

from pathlib import Path
from unittest.mock import patch

from ootp_radio.cli import main
from ootp_radio.models import (
    BroadcastIssue,
    BroadcastPlan,
    BroadcastSection,
    BroadcastSegment,
    GameDayEvent,
    GameFiles,
    GameHighlights,
    GameResult,
    LeagueSlate,
    NewsMessage,
    NewsPreview,
    OffDayBroadcastPlan,
    OffDayEvent,
    SelectedNewsMessage,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "game_1596" / "game_box_1596.html"
)


def _create_live_recap_save(tmp_path: Path) -> Path:
    save_dir = tmp_path / "Live League With Spaces.lg"
    (save_dir / "replays").mkdir(parents=True)
    box_scores_dir = save_dir / "news" / "html" / "box_scores"
    box_scores_dir.mkdir(parents=True)
    (save_dir / "replays" / "replay_1596.rpl").write_bytes(b"replay")
    (box_scores_dir / "game_box_1596.html").write_bytes(FIXTURE_PATH.read_bytes())
    return save_dir


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
    assert "Now, around the league" not in output


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


def test_recap_latest_dry_run_prints_live_narration_without_speaking(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)

    with patch("ootp_radio.live_recap.ensure_game_files_stable"):
        with patch("ootp_radio.cli.MacSaySpeaker.speak") as speak:
            result = main(
                ["recap-latest", "--save-dir", str(save_dir), "--dry-run"]
            )

    output = capsys.readouterr().out
    speak.assert_not_called()
    assert result == 0
    assert output.startswith(
        "This is WBAL News Radio. Your Baltimore Orioles postgame report."
    )
    assert "Baltimore Gets 7-4 Win" in output
    assert "DJ Layton" in output


def test_recap_latest_sends_live_narration_to_speaker(tmp_path: Path) -> None:
    save_dir = _create_live_recap_save(tmp_path)

    with patch("ootp_radio.live_recap.ensure_game_files_stable"):
        with patch("ootp_radio.cli.MacSaySpeaker.speak") as speak:
            result = main(["recap-latest", "--save-dir", str(save_dir)])

    assert result == 0
    narration = speak.call_args.args[0]
    assert narration.startswith(
        "This is WBAL News Radio. Your Baltimore Orioles postgame report."
    )
    assert "DJ Layton" in narration


def test_recap_latest_can_append_other_scores_without_repeating_own_game(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    results = [
        GameResult(1596, "08/01/2032", "Baltimore Orioles", 7, "Detroit Tigers", 4),
        GameResult(1600, "08/01/2032", "Seattle Mariners", 10, "Texas Rangers", 3),
    ]

    with patch("ootp_radio.live_recap.ensure_game_files_stable"):
        with patch(
            "ootp_radio.live_recap.discover_same_slate_results",
            return_value=results,
        ):
            result = main(
                [
                    "recap-latest",
                    "--save-dir",
                    str(save_dir),
                    "--around-league",
                    "--dry-run",
                ]
            )

    output = capsys.readouterr().out
    assert result == 0
    assert "Now, around the league." in output
    assert "The Seattle Mariners defeated the Texas Rangers, 10 to 3." in output
    assert "The Baltimore Orioles defeated the Detroit Tigers" not in output


def test_watch_stops_cleanly_on_keyboard_interrupt(tmp_path: Path, capsys) -> None:
    save_dir = tmp_path / "League.lg"

    with patch("ootp_radio.cli.RecapWatcher.run", side_effect=KeyboardInterrupt):
        result = main(["watch", "--save-dir", str(save_dir)])

    assert result == 0
    assert "watcher_stopped" in capsys.readouterr().err


def test_scores_latest_prints_count_and_deterministic_sentences(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    game_files = GameFiles(
        game_id=1596,
        replay_path=save_dir / "replays" / "replay_1596.rpl",
        box_score_path=(
            save_dir / "news" / "html" / "box_scores" / "game_box_1596.html"
        ),
        game_log_path=None,
        highlight_path=None,
    )
    results = [
        GameResult(1, "08/01/2032", "Seattle", 10, "Texas", 3),
        GameResult(2, "08/01/2032", "Miami", 0, "Philadelphia", 12),
    ]

    with patch("ootp_radio.cli.detect_latest_game") as detect:
        with patch("ootp_radio.cli.ensure_game_files_stable"):
            with patch(
                "ootp_radio.cli.discover_same_slate_results", return_value=results
            ):
                detect.return_value = game_files
                result = main(["scores-latest", "--save-dir", str(save_dir)])

    output = capsys.readouterr().out
    assert result == 0
    assert output.startswith("2 games found")
    assert "The Seattle defeated the Texas, 10 to 3." in output
    assert "The Philadelphia defeated the Miami, 12 to 0." in output


def test_news_preview_prints_counts_reason_and_clean_excerpt(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    game_files = GameFiles(
        1596,
        save_dir / "replays" / "replay_1596.rpl",
        save_dir / "news" / "html" / "box_scores" / "game_box_1596.html",
        None,
        None,
    )
    message = NewsMessage(
        2201,
        "Orioles News",
        "Baltimore Orioles announced a roster move.",
        (),
        Path("message2201.txt"),
        1,
    )
    preview = NewsPreview(
        examined_count=2,
        selected=(
            SelectedNewsMessage(message, ("configured team reference",)),
        ),
    )

    with patch("ootp_radio.cli.detect_latest_game", return_value=game_files):
        with patch("ootp_radio.cli.ensure_game_files_stable"):
            with patch("ootp_radio.cli.build_news_preview", return_value=preview):
                result = main(
                    [
                        "news-preview",
                        "--save-dir",
                        str(save_dir),
                        "--team-name",
                        "Baltimore Orioles",
                    ]
                )

    output = capsys.readouterr().out
    assert result == 0
    assert "2 recent messages examined" in output
    assert "1 selected" in output
    assert "1 filtered out" in output
    assert "Selected because: configured team reference" in output
    assert "Orioles News" in output
    assert "Baltimore Orioles announced a roster move." not in output
    assert "Preview:" not in output


def test_highlights_preview_prints_latest_sequences_without_speech(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    highlight_path = save_dir / "replays" / "highlight_1596.rpl"
    highlight_path.write_bytes(
        b"highlight_1596.rpl\x00Bradfield Jr.\x00"
        b"Cardozo delivers an RBI double.\x00"
        b"The score is 1-0, Orioles in front.\x00"
    )

    with patch("ootp_radio.cli.ensure_game_files_stable"):
        with patch("ootp_radio.cli.MacSaySpeaker.speak") as speak:
            with patch("ootp_radio.replay_strings.time.sleep"):
                result = main(
                    ["highlights-preview", "--save-dir", str(save_dir)]
                )

    output = capsys.readouterr().out
    speak.assert_not_called()
    assert result == 0
    assert output.startswith("Game 1596: 1 highlight sequences")
    assert "Highlight 1:" in output
    assert "Cardozo delivers an RBI double." in output
    assert not output.startswith("highlight_1596.rpl")


def test_highlights_preview_reports_missing_latest_highlight(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)

    with patch("ootp_radio.cli.ensure_game_files_stable"):
        result = main(["highlights-preview", "--save-dir", str(save_dir)])

    assert result == 2
    assert "has not created highlight_1596.rpl" in capsys.readouterr().err


def test_speak_highlights_uses_system_voice_and_separate_chunks(
    tmp_path: Path,
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    highlight_path = save_dir / "replays" / "highlight_1596.rpl"
    highlight_path.write_bytes(b"highlight")
    highlights = GameHighlights(
        game_id=1596,
        paragraphs=("First scoring play.", "Second scoring play."),
        source_path=highlight_path,
    )

    with patch("ootp_radio.cli.ensure_game_files_stable"):
        with patch(
            "ootp_radio.cli.parse_highlight_file", return_value=highlights
        ):
            with patch("ootp_radio.cli.MacSaySpeaker") as speaker_class:
                result = main(
                    ["speak-highlights", "--save-dir", str(save_dir)]
                )

    assert result == 0
    speaker_class.assert_called_once_with(voice=None, rate=None)
    spoken_chunks = [
        call.args[0] for call in speaker_class.return_value.speak.call_args_list
    ]
    assert spoken_chunks == [
        "Now, the game highlights.",
        "First scoring play.",
        "Second scoring play.",
    ]


def test_speak_highlights_dry_run_prints_without_speaking(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    highlight_path = save_dir / "replays" / "highlight_1596.rpl"
    highlight_path.write_bytes(b"highlight")
    highlights = GameHighlights(
        game_id=1596,
        paragraphs=("First scoring play.",),
        source_path=highlight_path,
    )

    with patch("ootp_radio.cli.ensure_game_files_stable"):
        with patch(
            "ootp_radio.cli.parse_highlight_file", return_value=highlights
        ):
            with patch("ootp_radio.cli.MacSaySpeaker.speak") as speak:
                result = main(
                    [
                        "speak-highlights",
                        "--save-dir",
                        str(save_dir),
                        "--dry-run",
                    ]
                )

    output = capsys.readouterr().out
    assert result == 0
    speak.assert_not_called()
    assert output == "Now, the game highlights.\n\nFirst scoring play.\n"


def test_broadcast_preview_prints_effective_order_sections_and_omissions(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    plan = BroadcastPlan(
        game_id=1596,
        requested_order=(
            BroadcastSegment.NEWS,
            BroadcastSegment.HIGHLIGHTS,
            BroadcastSegment.TEAM_RECAP,
        ),
        effective_order=(
            BroadcastSegment.HIGHLIGHTS,
            BroadcastSegment.TEAM_RECAP,
            BroadcastSegment.NEWS,
        ),
        sections=(
            BroadcastSection(
                BroadcastSegment.HIGHLIGHTS,
                ("The pitch...", "The runner scores."),
            ),
            BroadcastSection(
                BroadcastSegment.TEAM_RECAP,
                ("This is WBAL News Radio. Orioles win.",),
            ),
        ),
        issues=(
            BroadcastIssue(
                BroadcastSegment.NEWS,
                "no qualifying new MLB headlines were found",
            ),
        ),
    )
    game_files = GameFiles(
        1596,
        save_dir / "replays" / "replay_1596.rpl",
        save_dir / "news" / "html" / "box_scores" / "game_box_1596.html",
        None,
        None,
    )
    slate = LeagueSlate(
        "08/01/2032",
        (
            GameResult(
                1596,
                "08/01/2032",
                "Baltimore Orioles",
                7,
                "Detroit Tigers",
                4,
                3,
                10,
            ),
        ),
        1,
    )

    with patch(
        "ootp_radio.cli.detect_latest_radio_event",
        return_value=GameDayEvent(game_files, slate),
    ):
        with patch(
            "ootp_radio.cli.prepare_game_broadcast", return_value=plan
        ):
            result = main(
                [
                    "broadcast-preview",
                    "--save-dir",
                    str(save_dir),
                    "--team-name",
                    "Baltimore Orioles",
                    "--segment",
                    "news",
                    "--segment",
                    "highlights",
                    "--segment",
                    "team-recap",
                ]
            )

    output = capsys.readouterr().out
    assert result == 0
    assert "Effective order: highlights -> team-recap -> news" in output
    assert output.index("[highlights]") < output.index("[team-recap]")
    assert "The pitch...\n\nThe runner scores." in output
    assert "Skipped [news]" in output


def test_broadcast_preview_prints_off_day_scores_without_team_segments(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)
    slate = LeagueSlate(
        "08/04/2032",
        (GameResult(50, "08/04/2032", "Seattle", 5, "Texas", 3),),
        1,
    )
    plan = OffDayBroadcastPlan(
        date="08/04/2032",
        requested_order=(
            BroadcastSegment.HIGHLIGHTS,
            BroadcastSegment.SCORES,
        ),
        effective_order=(
            BroadcastSegment.HIGHLIGHTS,
            BroadcastSegment.SCORES,
        ),
        sections=(
            BroadcastSection(
                BroadcastSegment.SCORES,
                ("Around the league.", "The Seattle defeated the Texas, 5 to 3."),
            ),
        ),
        issues=(
            BroadcastIssue(
                BroadcastSegment.HIGHLIGHTS,
                "Baltimore Orioles did not play on 08/04/2032",
            ),
        ),
    )

    with patch(
        "ootp_radio.cli.detect_latest_radio_event",
        return_value=OffDayEvent(slate),
    ):
        with patch(
            "ootp_radio.cli.prepare_off_day_broadcast",
            return_value=plan,
        ):
            result = main(
                [
                    "broadcast-preview",
                    "--save-dir",
                    str(save_dir),
                    "--team-name",
                    "Baltimore Orioles",
                    "--segment",
                    "highlights",
                    "--segment",
                    "scores",
                ]
            )

    output = capsys.readouterr().out
    assert result == 0
    assert output.startswith("Off day for Baltimore Orioles on 08/04/2032")
    assert "Skipped [highlights]" in output
    assert "[scores]" in output


def test_watch_broadcast_builds_latest_wins_controller_and_stops_cleanly(
    tmp_path: Path, capsys
) -> None:
    save_dir = _create_live_recap_save(tmp_path)

    with patch("ootp_radio.cli.build_latest_wins_controller") as build:
        build.return_value.run.side_effect = KeyboardInterrupt
        result = main(
            [
                "watch-broadcast",
                "--save-dir",
                str(save_dir),
                "--team-name",
                "Baltimore Orioles",
                "--segment",
                "news",
                "--segment",
                "highlights",
                "--play-current",
            ]
        )

    assert result == 0
    build.assert_called_once_with(
        save_dir=save_dir,
        team_name="Baltimore Orioles",
        segments=(BroadcastSegment.NEWS, BroadcastSegment.HIGHLIGHTS),
        voice=None,
        rate=None,
        poll_interval_seconds=2.0,
        play_current=True,
    )
    build.return_value.stop_listening.assert_called_once()
    assert "broadcast_watcher_stopped" in capsys.readouterr().err


def test_gui_command_launches_desktop_entry_point() -> None:
    with patch("ootp_radio.cli._launch_gui", return_value=0) as launch:
        result = main(["gui"])

    assert result == 0
    launch.assert_called_once_with()

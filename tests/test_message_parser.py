"""Tests for message parsing, recent discovery, and conservative filtering."""

import os
from pathlib import Path

import pytest

from ootp_radio.message_parser import (
    MessageError,
    MessageBatchNotReadyError,
    MessageParseError,
    build_news_preview,
    discover_recent_messages,
    filter_messages,
    parse_message_file,
    parse_message_text,
    select_message,
)
from ootp_radio.models import GameFiles, GameResult, NewsMessage


def _message(
    document: str,
    *,
    message_id: int = 1,
) -> NewsMessage:
    return parse_message_text(
        document,
        message_id=message_id,
        source_path=Path(f"message{message_id}.txt"),
        modified_time_ns=1,
    )


def _create_message_batch(tmp_path: Path) -> tuple[GameFiles, Path, int]:
    save_dir = tmp_path / "League With Message Spaces.lg"
    replays_dir = save_dir / "replays"
    box_scores_dir = save_dir / "news" / "html" / "box_scores"
    messages_dir = save_dir / "messages"
    replays_dir.mkdir(parents=True)
    box_scores_dir.mkdir(parents=True)
    messages_dir.mkdir()
    replay = replays_dir / "replay_100.rpl"
    box_score = box_scores_dir / "game_box_100.html"
    replay.write_bytes(b"replay")
    box_score.write_text("box", encoding="utf-8")
    anchor_ns = 2_000_000_000_000
    os.utime(replay, ns=(anchor_ns, anchor_ns))
    return GameFiles(100, replay, box_score, None, None), messages_dir, anchor_ns


def test_parses_and_cleans_entity_references() -> None:
    message = _message(
        "Orioles Update\n"
        "<Yadier Munoz:player#130290> joined the "
        "<Baltimore Orioles:team#3>."
    )

    assert message.headline == "Orioles Update"
    assert message.body == "Yadier Munoz joined the Baltimore Orioles."
    parsed_references = [
        (reference.name, reference.entity_type, reference.entity_id)
        for reference in message.references
    ]
    assert parsed_references == [
        ("Yadier Munoz", "player", "130290"),
        ("Baltimore Orioles", "team", "3"),
    ]
    assert "<" not in message.body


def test_empty_headline_has_a_clear_error() -> None:
    with pytest.raises(MessageParseError, match="empty headline"):
        _message("\nBody text")


def test_invalid_message_filename_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "latest.txt"
    path.write_text("Headline\nBody", encoding="utf-8")

    with pytest.raises(MessageParseError, match="message2201.txt"):
        parse_message_file(path)


def test_explicit_major_league_baseball_message_is_selected() -> None:
    message = _message("League News\nMajor League Baseball announced a change.")

    selected = select_message(message, team_name="Baltimore Orioles")

    assert selected is not None
    assert selected.reasons == ("explicitly identifies Major League Baseball",)


def test_configured_team_reference_is_selected() -> None:
    message = _message(
        "Roster News\n<Baltimore Orioles:team#3> recalled a pitcher."
    )

    selected = select_message(message, team_name="Baltimore Orioles")

    assert selected is not None
    assert selected.reasons == ("configured team reference",)


def test_configured_team_injury_explains_selection() -> None:
    message = _message(
        "Orioles Injury\nThe Baltimore Orioles announced an injured player is out for 4 weeks."
    )

    selected = select_message(message, team_name="Baltimore Orioles")

    assert selected is not None
    assert selected.reasons == ("configured team injury",)


def test_other_mlb_team_story_is_selected_from_same_day_team_set() -> None:
    message = _message(
        "Busch Tags Marlins for 5 Hits\n"
        "<Michael Busch:player#21481> of the <Philadelphia Phillies:team#21> "
        "faced the <Miami Marlins:team#11>.\n\n"
        "<View Boxscore:box#1620>"
    )

    selected = select_message(
        message,
        team_name="Baltimore Orioles",
        mlb_team_names={"Philadelphia Phillies", "Miami Marlins"},
        mlb_game_ids={1620},
    )

    assert selected is not None
    assert selected.reasons == ("same-day MLB box-score story",)


def test_city_only_reference_is_selected_by_same_day_mlb_team_id() -> None:
    message = _message(
        "Washington Halts Guerrero Jr.'s Hitting Streak\n"
        "<Toronto:team#29> defeated <Washington:team#30>."
    )

    selected = select_message(
        message,
        team_name="Baltimore Orioles",
        mlb_team_ids={29, 30},
    )

    assert selected is not None
    assert selected.reasons == ("MLB team story",)


def test_al_or_nl_award_headline_is_selected() -> None:
    message = _message(
        "Abel Wins AL Top Pitcher Honors\n"
        "Mick Abel was chosen after an excellent month."
    )

    selected = select_message(message, team_name="Baltimore Orioles")

    assert selected is not None
    assert selected.reasons == ("MLB award",)


def test_minor_league_power_ranking_is_filtered_out() -> None:
    message = _message(
        "Weekly Team Power Rankings\n"
        "Here are the current team power rankings for Dominican Rookie League."
    )

    assert select_message(message, team_name="Baltimore Orioles") is None


def test_affiliate_name_does_not_count_as_configured_team_reference() -> None:
    message = _message(
        "Affiliate News\n"
        "<Baltimore Orioles Orange:team#186> announced a roster move."
    )

    assert select_message(message, team_name="Baltimore Orioles") is None


def test_mlb_ballpark_name_does_not_promote_minor_league_story() -> None:
    message = _message(
        "20 Games in a Row for Naranjo\n"
        "<Los Angeles (DSL):team#159> played at Miami Marlins Complex."
    )

    assert (
        select_message(
            message,
            team_name="Baltimore Orioles",
            mlb_team_names={"Miami Marlins"},
        )
        is None
    )


def test_plain_mlb_team_name_selects_story_without_team_reference() -> None:
    message = _message(
        "Seattle's Luke Stevenson Injured\n"
        "Luke Stevenson of the Seattle Mariners was injured in today's game."
    )

    selected = select_message(
        message,
        team_name="Baltimore Orioles",
        mlb_team_names={"Seattle Mariners"},
    )

    assert selected is not None
    assert selected.reasons == ("MLB team story",)


def test_empty_configured_team_name_is_rejected() -> None:
    message = _message("League News\nMajor League Baseball announced a change.")

    with pytest.raises(MessageError, match="Team name cannot be empty"):
        select_message(message, team_name="  ")


def test_mlb_power_ranking_is_selected_with_specific_reason() -> None:
    message = _message(
        "Weekly Team Power Rankings\n"
        "Here are the current team power rankings for Major League Baseball."
    )

    selected = select_message(message, team_name="Baltimore Orioles")

    assert selected is not None
    assert selected.reasons == ("MLB power rankings",)


def test_filter_reports_examined_selected_and_filtered_counts() -> None:
    messages = [
        _message("MLB News\nMajor League Baseball update.", message_id=1),
        _message("Minor News\nDominican Rookie League update.", message_id=2),
    ]

    preview = filter_messages(messages, team_name="Baltimore Orioles")

    assert preview.examined_count == 2
    assert len(preview.selected) == 1
    assert preview.filtered_count == 1


def test_discovers_only_messages_in_latest_timestamp_window(tmp_path: Path) -> None:
    game_files, messages_dir, anchor_ns = _create_message_batch(tmp_path)
    recent = messages_dir / "message101.txt"
    old = messages_dir / "message102.txt"
    recent.write_text("Recent\nBody", encoding="utf-8")
    old.write_text("Old\nBody", encoding="utf-8")
    os.utime(recent, ns=(anchor_ns + 1_000_000_000,) * 2)
    os.utime(old, ns=(anchor_ns + 31_000_000_000,) * 2)

    messages = discover_recent_messages(game_files, sleep=lambda _: None)

    assert [message.message_id for message in messages] == [101]
    assert "Message Spaces" in str(messages[0].source_path)


def test_changing_recent_message_reports_not_ready(tmp_path: Path) -> None:
    game_files, messages_dir, anchor_ns = _create_message_batch(tmp_path)
    message_path = messages_dir / "message101.txt"
    message_path.write_text("Headline\nBody", encoding="utf-8")
    os.utime(message_path, ns=(anchor_ns, anchor_ns))

    def change_message(_: float) -> None:
        message_path.write_text("Headline\nA larger changing body", encoding="utf-8")

    with pytest.raises(MessageBatchNotReadyError, match="still being written"):
        discover_recent_messages(game_files, sleep=change_message)


def test_build_preview_combines_discovery_and_filtering(tmp_path: Path) -> None:
    game_files, messages_dir, anchor_ns = _create_message_batch(tmp_path)
    selected = messages_dir / "message101.txt"
    filtered = messages_dir / "message102.txt"
    selected.write_text(
        "League News\nMajor League Baseball announced an update.",
        encoding="utf-8",
    )
    filtered.write_text("Minor News\nA rookie league update.", encoding="utf-8")
    os.utime(selected, ns=(anchor_ns, anchor_ns))
    os.utime(filtered, ns=(anchor_ns, anchor_ns))

    preview = build_news_preview(
        game_files,
        team_name="Baltimore Orioles",
        sleep=lambda _: None,
        mlb_results=[
            GameResult(100, None, "Baltimore Orioles", 5, "Detroit Tigers", 4)
        ],
    )

    assert preview.examined_count == 2
    assert len(preview.selected) == 1
    assert preview.filtered_count == 1

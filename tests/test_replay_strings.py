"""Tests for experimental binary highlight-commentary extraction."""

from pathlib import Path

import pytest

from ootp_radio.replay_strings import (
    HighlightNotReadyError,
    HighlightParseError,
    extract_highlight_paragraphs,
    extract_printable_strings,
    parse_highlight_file,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "game_1596" / "highlight_1596.rpl"
)


def test_extracts_ordered_ascii_and_utf8_strings() -> None:
    data = b"\x00First line.\x00Caf\xc3\xa9 wins!\x00"

    assert extract_printable_strings(data) == ("First line.", "Café wins!")


def test_groups_commentary_and_filters_standalone_roster_names() -> None:
    data = (
        b"highlight_10.rpl\x00Bradfield Jr.\x00"
        b"At the plate is Thomas Sosa...\x00"
        b"versus the Tigers he's batting .263 --\x00"
        b"5 hits in 19 at-bats.\x00ff&?\x00"
        b"Cardozo delivers an RBI double.\x00"
        b"The score is 1-0, Orioles in front.\x00"
        b"ff&?\x00Pitcher\x00Bradfield Jr.\x00"
        b"Taking third is Bradfield Jr....\x00"
    )

    paragraphs = extract_highlight_paragraphs(data)

    assert paragraphs == (
        "At the plate is Thomas Sosa... versus the Tigers he's batting .263 -- "
        "5 hits in 19 at-bats. Cardozo delivers an RBI double. "
        "The score is 1-0, Orioles in front.",
        "Taking third is Bradfield Jr....",
    )


def test_game_1596_fixture_contains_known_highlights_without_filename() -> None:
    highlights = parse_highlight_file(FIXTURE_PATH, sleep=lambda _: None)
    preview = "\n\n".join(highlights.paragraphs)

    assert highlights.game_id == 1596
    assert "Cardozo delivers an RBI double." in preview
    assert "The score is 1-0, Orioles in front." in preview
    assert "It's a 2-RBI double by Sosa." in preview
    assert "The Orioles add to their lead -- it's 5-1." in preview
    assert not preview.startswith("highlight_1596.rpl")
    assert "\n\nBradfield Jr.\n\n" not in f"\n\n{preview}\n\n"


def test_file_without_commentary_has_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "highlight_12.rpl"
    path.write_bytes(b"OOTP\x00metadata\x00")

    with pytest.raises(HighlightParseError, match="No readable highlight"):
        parse_highlight_file(path, sleep=lambda _: None)


def test_invalid_highlight_filename_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "latest.rpl"
    path.write_bytes(b"A valid commentary sentence.")

    with pytest.raises(HighlightParseError, match="highlight_1596.rpl"):
        parse_highlight_file(path, sleep=lambda _: None)


def test_changing_highlight_reports_not_ready(tmp_path: Path) -> None:
    path = tmp_path / "highlight_12.rpl"
    path.write_bytes(b"Original commentary sentence.")

    def change_highlight(_: float) -> None:
        path.write_bytes(b"A larger changing commentary sentence.")

    with pytest.raises(HighlightNotReadyError, match="still being written"):
        parse_highlight_file(path, sleep=change_highlight)

"""Tests for marked OOTP recap extraction and cleanup."""

from pathlib import Path

import pytest

from ootp_radio.recap_parser import MissingRecapMarkerError, parse_recap_html

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "game_1596" / "game_box_1596.html"
)


def _parse_fixture():
    return parse_recap_html(FIXTURE_PATH.read_text(encoding="utf-8"), game_id=1596)


def test_extracts_exact_subject() -> None:
    assert _parse_fixture().subject == "Baltimore Gets 7-4 Win"


def test_body_contains_expected_game_facts() -> None:
    body = _parse_fixture().body

    for expected_text in (
        "DJ Layton",
        "Parker Hutyra",
        "Cody Laweryson",
        "Thomas Sosa",
        "63-43",
    ):
        assert expected_text in body


def test_removes_html_tags_and_recap_comments() -> None:
    recap = _parse_fixture()
    output = f"{recap.subject}\n{recap.body}"

    assert "<a href=" not in output
    assert "<!--RECAP" not in output
    assert "<br>" not in output


def test_double_breaks_become_paragraph_spacing() -> None:
    body = _parse_fixture().body

    assert "chances.\n\nWho knows how it might've ended" in body
    assert "at-bats.\n\n\"Our goal is to improve" in body


def test_decodes_html_entities() -> None:
    document = """
    <!--RECAP_SUBJECT_START-->A &amp; B<!--RECAP_SUBJECT_END-->
    <!--RECAP_TEXT_START-->One&nbsp;team said &quot;hello.&quot;<!--RECAP_TEXT_END-->
    """

    recap = parse_recap_html(document, game_id=1)

    assert recap.subject == "A & B"
    assert recap.body == 'One team said "hello."'


def test_missing_markers_raise_a_clear_typed_error() -> None:
    document = """
    <!--RECAP_SUBJECT_START-->A subject<!--RECAP_SUBJECT_END-->
    This document has no recap text markers.
    """

    with pytest.raises(MissingRecapMarkerError, match="Missing recap text start marker"):
        parse_recap_html(document, game_id=1)


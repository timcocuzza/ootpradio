"""Extract OOTP's existing prose recap from a game box score."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from ootp_radio.models import GameRecap

_SUBJECT_START = "<!--RECAP_SUBJECT_START-->"
_SUBJECT_END = "<!--RECAP_SUBJECT_END-->"
_TEXT_START = "<!--RECAP_TEXT_START-->"
_TEXT_END = "<!--RECAP_TEXT_END-->"
_GAME_BOX_FILENAME = re.compile(r"game_box_(\d+)\.html")


class RecapParseError(ValueError):
    """Base class for expected recap parsing failures."""


class MissingRecapMarkerError(RecapParseError):
    """Raised when an expected recap boundary marker is absent."""


class EmptyRecapSectionError(RecapParseError):
    """Raised when a marked recap section has no readable text."""


class _RecapTextExtractor(HTMLParser):
    """Collect visible text while preserving explicit OOTP line breaks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag.lower() == "br":
            self.parts.append("\n")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"div", "li", "p", "tr"}:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _extract_section(
    document: str, start_marker: str, end_marker: str, section_name: str
) -> str:
    start_index = document.find(start_marker)
    if start_index == -1:
        raise MissingRecapMarkerError(
            f"Missing {section_name} start marker: {start_marker}"
        )

    content_start = start_index + len(start_marker)
    end_index = document.find(end_marker, content_start)
    if end_index == -1:
        raise MissingRecapMarkerError(
            f"Missing {section_name} end marker: {end_marker}"
        )

    return document[content_start:end_index]


def _visible_text(fragment: str) -> str:
    parser = _RecapTextExtractor()
    parser.feed(fragment)
    parser.close()

    text = "".join(parser.parts).replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_recap_html(document: str, game_id: int) -> GameRecap:
    """Parse marked recap content from an OOTP box-score document."""
    subject_fragment = _extract_section(
        document, _SUBJECT_START, _SUBJECT_END, "recap subject"
    )
    body_fragment = _extract_section(document, _TEXT_START, _TEXT_END, "recap text")

    subject = " ".join(_visible_text(subject_fragment).split())
    body = _visible_text(body_fragment)

    if not subject:
        raise EmptyRecapSectionError("The recap subject markers contain no text.")
    if not body:
        raise EmptyRecapSectionError("The recap text markers contain no text.")

    return GameRecap(game_id=game_id, subject=subject, body=body)


def parse_recap_file(path: Path | str) -> GameRecap:
    """Read and parse an OOTP game-box file."""
    box_score_path = Path(path)
    filename_match = _GAME_BOX_FILENAME.fullmatch(box_score_path.name)
    if filename_match is None:
        raise RecapParseError(
            "Expected a box-score filename like game_box_1596.html, "
            f"but received '{box_score_path.name}'."
        )

    try:
        document = box_score_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise RecapParseError(
            f"The box score '{box_score_path}' is not valid UTF-8 text."
        ) from error
    except OSError as error:
        detail = error.strerror or str(error)
        raise RecapParseError(
            f"Could not read box score '{box_score_path}': {detail}."
        ) from error

    return parse_recap_html(document, game_id=int(filename_match.group(1)))


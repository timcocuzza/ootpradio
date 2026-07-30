"""Experimentally extract readable commentary from OOTP highlight replays."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG

from ootp_radio.models import GameHighlights

_HIGHLIGHT_FILENAME = re.compile(r"highlight_(\d+)\.rpl")
_STANDALONE_NAME = re.compile(
    r"[A-Z][A-Za-z'\-]*(?: (?:[A-Z][A-Za-z'\-]*|Jr\.|Sr\.|II|III|IV))*"
)
_COMMENTARY_PUNCTUATION = frozenset(" .,!?'\"()/:;%+-")
_PARAGRAPH_BREAK_RUNS = 3


class HighlightError(RuntimeError):
    """Base class for expected highlight-preview failures."""


class HighlightNotAvailableError(HighlightError):
    """Raised when OOTP did not create a highlight file for the game."""


class HighlightNotReadyError(HighlightError):
    """Raised when a highlight file changes while being inspected."""


class HighlightParseError(HighlightError):
    """Raised when no narration-friendly commentary can be extracted."""


@dataclass(frozen=True)
class _PrintableRun:
    text: str
    start: int
    end: int


def _utf8_character(data: bytes, index: int) -> tuple[str, int] | None:
    """Return one printable UTF-8 character and its byte length."""
    first_byte = data[index]
    if 0x20 <= first_byte <= 0x7E:
        return chr(first_byte), 1
    if 0xC2 <= first_byte <= 0xDF:
        width = 2
    elif 0xE0 <= first_byte <= 0xEF:
        width = 3
    elif 0xF0 <= first_byte <= 0xF4:
        width = 4
    else:
        return None

    encoded = data[index : index + width]
    if len(encoded) != width:
        return None
    try:
        character = encoded.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return (character, width) if character.isprintable() else None


def _printable_runs(data: bytes, *, minimum_length: int) -> tuple[_PrintableRun, ...]:
    if minimum_length <= 0:
        raise ValueError("minimum_length must be greater than zero")

    runs: list[_PrintableRun] = []
    characters: list[str] = []
    run_start = 0
    index = 0

    def finish_run(end: int) -> None:
        if len(characters) >= minimum_length:
            runs.append(_PrintableRun("".join(characters), run_start, end))
        characters.clear()

    while index < len(data):
        decoded = _utf8_character(data, index)
        if decoded is None:
            finish_run(index)
            index += 1
            continue

        if not characters:
            run_start = index
        character, width = decoded
        characters.append(character)
        index += width

    finish_run(len(data))
    return tuple(runs)


def extract_printable_strings(
    data: bytes, *, minimum_length: int = 4
) -> tuple[str, ...]:
    """Extract ordered printable ASCII and UTF-8 runs from binary data."""
    return tuple(
        run.text for run in _printable_runs(data, minimum_length=minimum_length)
    )


def _is_commentary(text: str) -> bool:
    text = text.strip()
    if len(text) < 8 or text.endswith(".rpl"):
        return False
    if text == "SUBSTITUTION...":
        return True
    has_sentence_ending = text[-1] in ".!?" or text.endswith("--")
    if not has_sentence_ending or not any(
        character.islower() for character in text
    ):
        return False
    if _STANDALONE_NAME.fullmatch(text) is not None:
        return False
    return all(
        character.isalnum() or character in _COMMENTARY_PUNCTUATION
        for character in text
    )


def extract_highlight_paragraphs(data: bytes) -> tuple[str, ...]:
    """Filter printable runs and group adjacent commentary into plays."""
    paragraphs: list[str] = []
    current_lines: list[str] = []
    rejected_runs = 0

    for run in _printable_runs(data, minimum_length=4):
        text = " ".join(run.text.split())
        if _is_commentary(text):
            if current_lines and rejected_runs >= _PARAGRAPH_BREAK_RUNS:
                paragraphs.append(" ".join(current_lines))
                current_lines = []
            current_lines.append(text)
            rejected_runs = 0
            continue
        if current_lines:
            rejected_runs += 1

    if current_lines:
        paragraphs.append(" ".join(current_lines))
    return tuple(paragraphs)


def parse_highlight_bytes(
    data: bytes, *, game_id: int, source_path: Path
) -> GameHighlights:
    """Create a typed highlight preview from stable binary data."""
    paragraphs = extract_highlight_paragraphs(data)
    if not paragraphs:
        raise HighlightParseError(
            f"No readable highlight commentary was found in '{source_path.name}'."
        )
    return GameHighlights(
        game_id=game_id,
        paragraphs=paragraphs,
        source_path=source_path,
    )


def _file_snapshot(path: Path) -> tuple[int, int]:
    try:
        path_stat = path.stat()
    except FileNotFoundError as error:
        raise HighlightNotAvailableError(
            f"Highlight replay is not available: '{path}'."
        ) from error
    except OSError as error:
        raise HighlightError(f"Could not inspect '{path}': {error}.") from error
    if not S_ISREG(path_stat.st_mode):
        raise HighlightNotAvailableError(
            f"Highlight replay is not a regular file: '{path}'."
        )
    return path_stat.st_size, path_stat.st_mtime_ns


def parse_highlight_file(
    path: Path | str,
    *,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> GameHighlights:
    """Read a stable ``highlight_<ID>.rpl`` file without modifying it."""
    if poll_interval_seconds < 0:
        raise ValueError("poll_interval_seconds cannot be negative")

    highlight_path = Path(path)
    filename_match = _HIGHLIGHT_FILENAME.fullmatch(highlight_path.name)
    if filename_match is None:
        raise HighlightParseError(
            "Expected a filename like highlight_1596.rpl, "
            f"but received '{highlight_path.name}'."
        )

    first_snapshot = _file_snapshot(highlight_path)
    sleep(poll_interval_seconds)
    try:
        data = highlight_path.read_bytes()
    except OSError as error:
        raise HighlightError(f"Could not read '{highlight_path}': {error}.") from error
    second_snapshot = _file_snapshot(highlight_path)
    if second_snapshot != first_snapshot or len(data) != second_snapshot[0]:
        raise HighlightNotReadyError(
            f"{highlight_path.name} is still being written by OOTP. "
            "Try again in a moment."
        )

    return parse_highlight_bytes(
        data,
        game_id=int(filename_match.group(1)),
        source_path=highlight_path,
    )

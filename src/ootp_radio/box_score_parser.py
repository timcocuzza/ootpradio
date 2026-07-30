"""Parse final scores and discover a played game's same-slate MLB results."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from stat import S_ISREG

from ootp_radio.models import GameFiles, GameResult

_GAME_BOX_FILENAME = re.compile(r"game_box_(\d+)\.html")
_MLB_TITLE = re.compile(
    r"MLB Box Score,\s*(?P<away>.+?)\s+at\s+(?P<home>.+?),\s*"
    r"(?P<date>\d{2}/\d{2}/\d{4})"
)
_GAME_ID_TEXT = re.compile(r"GAME\s+ID:\s*(\d+)", re.IGNORECASE)
_TEAM_LINK = re.compile(r"(?:\.\./)?teams/team_(\d+)\.html")
_TEAM_RECORD = re.compile(r"\s+\(\d+-\d+(?:-\d+)?\)\s*$")


class BoxScoreError(RuntimeError):
    """Base class for expected box-score and slate failures."""


class BoxScoreParseError(BoxScoreError):
    """Raised when an MLB box score lacks required final-score fields."""


class NotMajorLeagueBoxScoreError(BoxScoreError):
    """Raised when a box score is not from Major League Baseball."""


class ScoreSlateNotReadyError(BoxScoreError):
    """Raised when one or more same-slate box scores are still changing."""


@dataclass
class _TableState:
    rows: list[list[str]] = field(default_factory=list)
    current_row: list[str] | None = None
    current_cell_parts: list[str] | None = None


class _BoxScoreHTMLParser(HTMLParser):
    """Collect the document title and rows from each individual HTML table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._in_title = False
        self._table_stack: list[_TableState] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "table":
            self._table_stack.append(_TableState())
        elif tag == "tr" and self._table_stack:
            self._table_stack[-1].current_row = []
        elif tag in {"td", "th"} and self._table_stack:
            state = self._table_stack[-1]
            if state.current_row is not None:
                state.current_cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._table_stack:
            cell_parts = self._table_stack[-1].current_cell_parts
            if cell_parts is not None:
                cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag in {"td", "th"} and self._table_stack:
            state = self._table_stack[-1]
            if state.current_row is not None and state.current_cell_parts is not None:
                state.current_row.append(
                    " ".join("".join(state.current_cell_parts).split())
                )
            state.current_cell_parts = None
        elif tag == "tr" and self._table_stack:
            state = self._table_stack[-1]
            if state.current_row is not None:
                state.rows.append(state.current_row)
            state.current_row = None
            state.current_cell_parts = None
        elif tag == "table" and self._table_stack:
            state = self._table_stack.pop()
            self.tables.append(state.rows)


def _parse_title(parser: _BoxScoreHTMLParser) -> tuple[str, str, str]:
    title = " ".join("".join(parser.title_parts).split())
    title_match = _MLB_TITLE.fullmatch(title)
    if title_match is None:
        raise NotMajorLeagueBoxScoreError(
            f"Document title is not an MLB box score: '{title or 'missing title'}'."
        )
    return (
        title_match.group("away"),
        title_match.group("home"),
        title_match.group("date"),
    )


def _team_without_record(value: str) -> str:
    return _TEAM_RECORD.sub("", value).strip()


def _parse_score(value: str, *, team_name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise BoxScoreParseError(
            f"Final score for {team_name} is not an integer: '{value}'."
        ) from error


def _find_line_score(
    tables: list[list[list[str]]], *, away_team: str, home_team: str
) -> tuple[int, int]:
    for table in tables:
        for row_index, header in enumerate(table):
            if len(header) < 4 or header[-3:] != ["R", "H", "E"]:
                continue
            if row_index + 2 >= len(table):
                continue

            away_row = table[row_index + 1]
            home_row = table[row_index + 2]
            runs_index = len(header) - 3
            if len(away_row) <= runs_index or len(home_row) <= runs_index:
                continue
            if _team_without_record(away_row[0]) != away_team:
                continue
            if _team_without_record(home_row[0]) != home_team:
                continue

            return (
                _parse_score(away_row[runs_index], team_name=away_team),
                _parse_score(home_row[runs_index], team_name=home_team),
            )

    raise BoxScoreParseError(
        f"Could not find the final R/H/E line score for {away_team} at {home_team}."
    )


def _find_team_ids(document: str) -> tuple[int | None, int | None]:
    """Read the away and home IDs from their first unique team links."""
    unique_ids = tuple(dict.fromkeys(_TEAM_LINK.findall(document)))
    if len(unique_ids) < 2:
        return None, None
    return int(unique_ids[0]), int(unique_ids[1])


def parse_box_score_html(document: str, *, game_id: int) -> GameResult:
    """Parse one final MLB result from OOTP box-score HTML."""
    parser = _BoxScoreHTMLParser()
    parser.feed(document)
    parser.close()

    away_team, home_team, game_date = _parse_title(parser)
    document_game_id = _GAME_ID_TEXT.search(document)
    if document_game_id is not None and int(document_game_id.group(1)) != game_id:
        raise BoxScoreParseError(
            f"Box score says game {document_game_id.group(1)}, but its filename "
            f"identifies game {game_id}."
        )

    away_score, home_score = _find_line_score(
        parser.tables,
        away_team=away_team,
        home_team=home_team,
    )
    away_team_id, home_team_id = _find_team_ids(document)
    return GameResult(
        game_id=game_id,
        date=game_date,
        away_team=away_team,
        away_score=away_score,
        home_team=home_team,
        home_score=home_score,
        away_team_id=away_team_id,
        home_team_id=home_team_id,
    )


def parse_box_score_file(path: Path | str) -> GameResult:
    """Read and parse an OOTP ``game_box_<ID>.html`` file."""
    box_score_path = Path(path)
    filename_match = _GAME_BOX_FILENAME.fullmatch(box_score_path.name)
    if filename_match is None:
        raise BoxScoreParseError(
            "Expected a filename like game_box_1596.html, "
            f"but received '{box_score_path.name}'."
        )
    try:
        document = box_score_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise BoxScoreParseError(
            f"Box score '{box_score_path}' is not valid UTF-8 text."
        ) from error
    except OSError as error:
        raise BoxScoreParseError(
            f"Could not read box score '{box_score_path}': {error}."
        ) from error
    return parse_box_score_html(document, game_id=int(filename_match.group(1)))


def _file_metadata(path: Path) -> tuple[int, int]:
    try:
        path_stat = path.stat()
    except FileNotFoundError as error:
        raise ScoreSlateNotReadyError(
            f"{path.name} disappeared while the score slate was being checked."
        ) from error
    except OSError as error:
        raise BoxScoreError(f"Could not inspect '{path}': {error}.") from error
    if not S_ISREG(path_stat.st_mode):
        raise BoxScoreError(f"Expected '{path}' to be a regular file.")
    return path_stat.st_size, path_stat.st_mtime_ns


def discover_same_slate_results(
    game_files: GameFiles,
    *,
    window_seconds: float = 5.0,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> list[GameResult]:
    """Find stable MLB box scores written near the played replay's timestamp."""
    if window_seconds < 0:
        raise ValueError("window_seconds cannot be negative")
    if poll_interval_seconds < 0:
        raise ValueError("poll_interval_seconds cannot be negative")

    try:
        replay_mtime_ns = game_files.replay_path.stat().st_mtime_ns
        entries = list(game_files.box_score_path.parent.iterdir())
    except OSError as error:
        raise BoxScoreError(f"Could not inspect the score slate: {error}.") from error

    window_ns = int(window_seconds * 1_000_000_000)
    first_metadata: dict[Path, tuple[int, int]] = {}
    for entry in entries:
        if _GAME_BOX_FILENAME.fullmatch(entry.name) is None:
            continue
        metadata = _file_metadata(entry)
        if abs(metadata[1] - replay_mtime_ns) <= window_ns:
            first_metadata[entry] = metadata

    if game_files.box_score_path not in first_metadata:
        first_metadata[game_files.box_score_path] = _file_metadata(
            game_files.box_score_path
        )

    sleep(poll_interval_seconds)
    for path, metadata in first_metadata.items():
        if _file_metadata(path) != metadata:
            raise ScoreSlateNotReadyError(
                f"{path.name} is still being written by OOTP. Try again in a moment."
            )

    played_result = parse_box_score_file(game_files.box_score_path)
    results_by_id = {played_result.game_id: played_result}
    for path in first_metadata:
        if path == game_files.box_score_path:
            continue
        try:
            result = parse_box_score_file(path)
        except NotMajorLeagueBoxScoreError:
            continue
        if result.date == played_result.date:
            results_by_id[result.game_id] = result

    return [results_by_id[game_id] for game_id in sorted(results_by_id)]

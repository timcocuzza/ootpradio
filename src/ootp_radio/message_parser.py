"""Parse, discover, and conservatively filter recent OOTP messages."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from stat import S_ISREG

from ootp_radio.box_score_parser import discover_same_slate_results
from ootp_radio.models import (
    GameFiles,
    GameResult,
    MessageReference,
    NewsMessage,
    NewsPreview,
    SelectedNewsMessage,
)

_MESSAGE_FILENAME = re.compile(r"message(\d+)\.txt")
_ENTITY_REFERENCE = re.compile(
    r"<([^:<>]+):(player|team|league|coach|box)#([^>]+)>"
)
_INJURY_TERMS = (
    "injur",
    "disabled list",
    "out for",
    "miss the rest",
    "sidelined",
)
_TRANSACTION_TERMS = (
    "acquire",
    "contract",
    "designated for assignment",
    "optioned",
    "release",
    "sign",
    "trade",
    "waiver",
)
_AWARD_TERMS = (
    "award",
    "batter of the month",
    "honor",
    "pitcher of the month",
    "player of the week",
    "rookie of the month",
    "top pitcher",
    "top player",
    "top starter",
    "trophy",
)


class MessageError(RuntimeError):
    """Base class for expected message preview failures."""


class MessageParseError(MessageError):
    """Raised when an individual message cannot be parsed."""


class MessageBatchNotReadyError(MessageError):
    """Raised when recent message files are still changing."""


def _normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", value):
        normalized = " ".join(paragraph.split())
        if normalized:
            paragraphs.append(normalized)
    return "\n\n".join(paragraphs)


def _clean_references(value: str) -> str:
    return _ENTITY_REFERENCE.sub(lambda match: match.group(1), value)


def parse_message_text(
    document: str,
    *,
    message_id: int,
    source_path: Path,
    modified_time_ns: int,
) -> NewsMessage:
    """Parse a headline, cleaned body, and entity references."""
    document = document.lstrip("\ufeff")
    first_line, separator, remaining = document.partition("\n")
    headline = _normalize_text(_clean_references(first_line))
    if not headline:
        raise MessageParseError(f"Message {message_id} has an empty headline.")

    references = tuple(
        MessageReference(
            name=match.group(1),
            entity_type=match.group(2),
            entity_id=match.group(3),
        )
        for match in _ENTITY_REFERENCE.finditer(document)
    )
    body_source = remaining if separator else ""
    body = _normalize_text(_clean_references(body_source))
    return NewsMessage(
        message_id=message_id,
        headline=headline,
        body=body,
        references=references,
        source_path=source_path,
        modified_time_ns=modified_time_ns,
    )


def parse_message_file(path: Path | str) -> NewsMessage:
    """Read and parse one ``message<ID>.txt`` file."""
    message_path = Path(path)
    filename_match = _MESSAGE_FILENAME.fullmatch(message_path.name)
    if filename_match is None:
        raise MessageParseError(
            "Expected a filename like message2201.txt, "
            f"but received '{message_path.name}'."
        )
    try:
        path_stat = message_path.stat()
        document = message_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise MessageParseError(
            f"Message '{message_path}' is not valid UTF-8 text."
        ) from error
    except OSError as error:
        raise MessageParseError(f"Could not read message '{message_path}': {error}.") from error
    return parse_message_text(
        document,
        message_id=int(filename_match.group(1)),
        source_path=message_path,
        modified_time_ns=path_stat.st_mtime_ns,
    )


def _file_metadata(path: Path) -> tuple[int, int]:
    try:
        path_stat = path.stat()
    except FileNotFoundError as error:
        raise MessageBatchNotReadyError(
            f"{path.name} disappeared while recent messages were being checked."
        ) from error
    except OSError as error:
        raise MessageError(f"Could not inspect '{path}': {error}.") from error
    if not S_ISREG(path_stat.st_mode):
        raise MessageError(f"Expected '{path}' to be a regular file.")
    return path_stat.st_size, path_stat.st_mtime_ns


def discover_recent_messages(
    game_files: GameFiles,
    *,
    window_seconds: float = 30.0,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> list[NewsMessage]:
    """Find stable messages written near the played replay's timestamp."""
    if window_seconds < 0:
        raise ValueError("window_seconds cannot be negative")
    if poll_interval_seconds < 0:
        raise ValueError("poll_interval_seconds cannot be negative")

    messages_dir = game_files.replay_path.parent.parent / "messages"
    try:
        replay_mtime_ns = game_files.replay_path.stat().st_mtime_ns
        entries = list(messages_dir.iterdir())
    except FileNotFoundError as error:
        raise MessageError(
            f"Messages directory does not exist: '{messages_dir}'."
        ) from error
    except OSError as error:
        raise MessageError(f"Could not inspect recent messages: {error}.") from error

    window_ns = int(window_seconds * 1_000_000_000)
    first_metadata: dict[Path, tuple[int, int]] = {}
    for entry in entries:
        if _MESSAGE_FILENAME.fullmatch(entry.name) is None:
            continue
        metadata = _file_metadata(entry)
        if abs(metadata[1] - replay_mtime_ns) <= window_ns:
            first_metadata[entry] = metadata

    sleep(poll_interval_seconds)
    for path, metadata in first_metadata.items():
        if _file_metadata(path) != metadata:
            raise MessageBatchNotReadyError(
                f"{path.name} is still being written by OOTP. Try again in a moment."
            )

    ordered_paths = sorted(
        first_metadata,
        key=lambda path: int(_MESSAGE_FILENAME.fullmatch(path.name).group(1)),
    )
    return [parse_message_file(path) for path in ordered_paths]


def select_message(
    message: NewsMessage,
    *,
    team_name: str,
    mlb_team_names: Collection[str] = (),
    mlb_team_ids: Collection[int] = (),
    mlb_game_ids: Collection[int] = (),
) -> SelectedNewsMessage | None:
    """Select a newly written headline when it can be tied to MLB."""
    team_name = team_name.strip()
    if not team_name:
        raise MessageError("Team name cannot be empty when filtering news.")

    searchable_text = f"{message.headline}\n{message.body}".casefold()
    headline = message.headline.casefold()
    team_name_folded = team_name.casefold()
    explicit_mlb = any(
        league_name in searchable_text
        for league_name in (
            "major league baseball",
            "american league",
            "national league",
        )
    )
    headline_has_league_abbreviation = bool(
        re.search(r"\b(?:AL|NL)\b", message.headline)
    )
    team_references = tuple(
        reference
        for reference in message.references
        if reference.entity_type == "team"
    )
    team_reference = any(
        reference.entity_type == "team"
        and reference.name.casefold() == team_name_folded
        for reference in team_references
    )
    def mentioned_outside_reference(name: str) -> bool:
        folded_name = name.casefold()
        total_mentions = searchable_text.count(folded_name)
        referenced_mentions = sum(
            reference.name.casefold().count(folded_name)
            for reference in message.references
        )
        return total_mentions > referenced_mentions

    plain_team_mention = mentioned_outside_reference(team_name)
    team_mentioned = team_reference or (
        not team_references and plain_team_mention
    )

    mlb_team_names_folded = {name.casefold() for name in mlb_team_names}
    mlb_team_ids_text = {str(team_id) for team_id in mlb_team_ids}
    mlb_team_reference = any(
        reference.entity_type == "team"
        and (
            reference.name.casefold() in mlb_team_names_folded
            or reference.entity_id in mlb_team_ids_text
        )
        for reference in message.references
    )
    mlb_team_mention = not team_references and any(
        mentioned_outside_reference(name) for name in mlb_team_names
    )
    mlb_box_reference = any(
        reference.entity_type == "box"
        and reference.entity_id in {str(game_id) for game_id in mlb_game_ids}
        for reference in message.references
    )
    award_story = any(term in searchable_text for term in _AWARD_TERMS)

    reasons: list[str] = []
    if explicit_mlb and "power rankings" in headline:
        reasons.append("MLB power rankings")
    elif award_story and (explicit_mlb or headline_has_league_abbreviation):
        reasons.append("MLB award")

    if team_mentioned:
        if any(term in searchable_text for term in _INJURY_TERMS):
            reasons.append("configured team injury")
        elif any(term in searchable_text for term in _TRANSACTION_TERMS):
            reasons.append("configured team transaction")
        else:
            reasons.append("configured team reference")
    elif mlb_box_reference and not reasons:
        reasons.append("same-day MLB box-score story")
    elif (mlb_team_reference or mlb_team_mention) and not reasons:
        reasons.append("MLB team story")
    elif explicit_mlb and not reasons:
        reasons.append("explicitly identifies Major League Baseball")

    if not reasons:
        return None
    return SelectedNewsMessage(message=message, reasons=tuple(reasons))


def filter_messages(
    messages: Sequence[NewsMessage],
    *,
    team_name: str,
    mlb_team_names: Collection[str] = (),
    mlb_team_ids: Collection[int] = (),
    mlb_game_ids: Collection[int] = (),
) -> NewsPreview:
    """Return selected messages and examined/filtered counts."""
    selected = tuple(
        selected_message
        for message in messages
        if (
            selected_message := select_message(
                message,
                team_name=team_name,
                mlb_team_names=mlb_team_names,
                mlb_team_ids=mlb_team_ids,
                mlb_game_ids=mlb_game_ids,
            )
        )
        is not None
    )
    return NewsPreview(examined_count=len(messages), selected=selected)


def build_news_preview(
    game_files: GameFiles,
    *,
    team_name: str,
    window_seconds: float = 30.0,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
    mlb_results: Sequence[GameResult] | None = None,
) -> NewsPreview:
    """Discover the latest stable message batch and filter it."""
    messages = discover_recent_messages(
        game_files,
        window_seconds=window_seconds,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    if mlb_results is None:
        mlb_results = discover_same_slate_results(
            game_files,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )
    mlb_team_names = {
        team_name
        for result in mlb_results
        for team_name in (result.away_team, result.home_team)
    }
    mlb_team_ids = {
        team_id
        for result in mlb_results
        for team_id in (result.away_team_id, result.home_team_id)
        if team_id is not None
    }
    mlb_game_ids = {result.game_id for result in mlb_results}
    return filter_messages(
        messages,
        team_name=team_name,
        mlb_team_names=mlb_team_names,
        mlb_team_ids=mlb_team_ids,
        mlb_game_ids=mlb_game_ids,
    )

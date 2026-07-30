"""Classify the newest stable OOTP day as a team game or an off day."""

from __future__ import annotations

from pathlib import Path

from ootp_radio.box_score_parser import (
    BoxScoreError,
    NotMajorLeagueBoxScoreError,
    ScoreSlateNotReadyError,
    discover_latest_mlb_slate,
    parse_box_score_file,
)
from ootp_radio.game_detector import (
    GameDetectionError,
    NoReplayFilesError,
    detect_latest_game,
    ensure_game_files_stable,
)
from ootp_radio.models import GameDayEvent, GameResult, LeagueSlate, OffDayEvent

RadioEvent = GameDayEvent | OffDayEvent


class RadioEventError(RuntimeError):
    """Base class for expected day-classification failures."""


class TeamResolutionError(RadioEventError):
    """Raised when a configured team cannot be mapped to one OOTP team ID."""


class RadioEventNotReadyError(RadioEventError):
    """Raised when a team result exists before its replay becomes stable."""


def _normalized_team_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def _matching_team_ids(
    results: tuple[GameResult, ...] | list[GameResult],
    *,
    team_name: str,
) -> set[int]:
    configured_name = _normalized_team_name(team_name)
    matches: set[int] = set()
    for result in results:
        for result_name, team_id in (
            (result.away_team, result.away_team_id),
            (result.home_team, result.home_team_id),
        ):
            if (
                team_id is not None
                and _normalized_team_name(result_name) == configured_name
            ):
                matches.add(team_id)
    return matches


def resolve_team_id(
    save_dir: Path | str,
    *,
    team_name: str,
    latest_slate: LeagueSlate | None = None,
) -> int:
    """Resolve an exact configured team name, searching newest results first."""
    if not team_name.strip():
        raise TeamResolutionError("Team name cannot be empty.")

    if latest_slate is not None:
        matches = _matching_team_ids(
            latest_slate.results,
            team_name=team_name,
        )
        if len(matches) == 1:
            return next(iter(matches))
        if len(matches) > 1:
            raise TeamResolutionError(
                f"Team name '{team_name}' matched multiple OOTP team IDs."
            )

    box_scores_dir = Path(save_dir) / "news" / "html" / "box_scores"
    try:
        candidates = sorted(
            (
                path
                for path in box_scores_dir.iterdir()
                if path.name.startswith("game_box_")
                and path.name.endswith(".html")
                and path.stem.removeprefix("game_box_").isdigit()
            ),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
            reverse=True,
        )
    except OSError as error:
        raise TeamResolutionError(
            f"Could not inspect box scores while resolving '{team_name}': "
            f"{error}."
        ) from error

    for path in candidates:
        try:
            result = parse_box_score_file(path)
        except NotMajorLeagueBoxScoreError:
            continue
        except BoxScoreError as error:
            raise TeamResolutionError(str(error)) from error
        matches = _matching_team_ids([result], team_name=team_name)
        if matches:
            return next(iter(matches))

    raise TeamResolutionError(
        f"Could not find an MLB team named '{team_name}' in this save. "
        "Use the complete OOTP team name, such as 'Baltimore Orioles'."
    )


class LatestRadioEventDetector:
    """Detect the newest day while retaining a safely resolved team identity."""

    def __init__(
        self,
        *,
        save_dir: Path | str,
        team_name: str,
        team_id: int | None = None,
    ) -> None:
        if not team_name.strip():
            raise ValueError("team_name cannot be empty")
        self.save_dir = Path(save_dir)
        self.team_name = team_name
        self.team_id = team_id

    def detect(self) -> RadioEvent:
        """Return a stable game/off-day event, or postpone an incomplete game."""
        try:
            slate = discover_latest_mlb_slate(self.save_dir)
        except ScoreSlateNotReadyError as error:
            raise RadioEventNotReadyError(str(error)) from error
        except BoxScoreError as error:
            raise RadioEventError(str(error)) from error
        if self.team_id is None:
            self.team_id = resolve_team_id(
                self.save_dir,
                team_name=self.team_name,
                latest_slate=slate,
            )

        team_results = tuple(
            result
            for result in slate.results
            if self.team_id in (result.away_team_id, result.home_team_id)
        )
        if not team_results:
            return OffDayEvent(slate=slate)

        matching_game_ids = {result.game_id for result in team_results}
        try:
            game_files = detect_latest_game(self.save_dir)
        except NoReplayFilesError as error:
            raise RadioEventNotReadyError(
                f"{self.team_name} played on {slate.date}, but its replay is "
                "not ready yet."
            ) from error
        except GameDetectionError as error:
            raise RadioEventError(str(error)) from error

        if game_files.game_id not in matching_game_ids:
            raise RadioEventNotReadyError(
                f"{self.team_name} played on {slate.date}, but replay files "
                "still point to an earlier game."
            )
        try:
            ensure_game_files_stable(game_files)
        except GameDetectionError as error:
            raise RadioEventNotReadyError(str(error)) from error
        return GameDayEvent(game_files=game_files, slate=slate)


def detect_latest_radio_event(
    save_dir: Path | str,
    *,
    team_name: str,
    team_id: int | None = None,
) -> RadioEvent:
    """Convenience wrapper for one-shot previews."""
    return LatestRadioEventDetector(
        save_dir=save_dir,
        team_name=team_name,
        team_id=team_id,
    ).detect()

"""Discover selectable MLB teams from recent read-only box scores."""

from __future__ import annotations

import re
from pathlib import Path

from ootp_radio.box_score_parser import (
    BoxScoreError,
    NotMajorLeagueBoxScoreError,
    parse_box_score_file,
)
from ootp_radio.models import TeamOption

_GAME_BOX_FILENAME = re.compile(r"game_box_(\d+)\.html")


class TeamDiscoveryError(RuntimeError):
    """Raised when the selected save cannot provide selectable MLB teams."""


def discover_mlb_teams(
    save_dir: Path | str,
    *,
    max_box_scores: int = 200,
) -> tuple[TeamOption, ...]:
    """Return newest-known names for MLB team IDs found in recent finals.

    More than one slate is inspected because the selected team can be absent
    from the latest slate on an off day. Newest files win if a team has been
    renamed or relocated. Malformed/in-progress candidates are skipped because
    team selection should remain usable while OOTP writes a new result.
    """
    if max_box_scores <= 0:
        raise ValueError("max_box_scores must be greater than zero")

    box_scores_dir = Path(save_dir) / "news" / "html" / "box_scores"
    try:
        candidates = []
        for path in box_scores_dir.iterdir():
            match = _GAME_BOX_FILENAME.fullmatch(path.name)
            if match is None:
                continue
            try:
                modified_time_ns = path.stat().st_mtime_ns
            except FileNotFoundError:
                continue
            candidates.append((modified_time_ns, int(match.group(1)), path))
    except FileNotFoundError as error:
        raise TeamDiscoveryError(
            f"The box-scores directory does not exist: '{box_scores_dir}'."
        ) from error
    except OSError as error:
        raise TeamDiscoveryError(
            f"Could not inspect teams in '{box_scores_dir}': {error}."
        ) from error

    teams_by_id: dict[int, TeamOption] = {}
    for _, _, path in sorted(candidates, reverse=True)[:max_box_scores]:
        try:
            result = parse_box_score_file(path)
        except (NotMajorLeagueBoxScoreError, BoxScoreError):
            continue
        for team_id, team_name in (
            (result.away_team_id, result.away_team),
            (result.home_team_id, result.home_team),
        ):
            if team_id is None or team_id in teams_by_id:
                continue
            teams_by_id[team_id] = TeamOption(
                team_id=team_id,
                name=team_name,
            )

    if not teams_by_id:
        raise TeamDiscoveryError(
            "No MLB teams with OOTP team IDs were found in recent box scores. "
            "Complete at least one MLB game, then choose this save again."
        )
    return tuple(sorted(teams_by_id.values(), key=lambda team: team.name.casefold()))

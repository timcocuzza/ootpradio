"""Build narration text from cleaned OOTP data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from ootp_radio.models import GameRecap, GameResult

TEAM_RADIO_STATIONS: Mapping[str, str] = MappingProxyType(
    {
        "Baltimore Orioles": "WBAL News Radio",
    }
)
TEAM_NARRATION_ALIASES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "Baltimore Orioles": ("Baltimore", "Orioles"),
    }
)


def _finish_sentence(text: str) -> str:
    text = text.strip()
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _find_mapped_team(
    recap: GameRecap, team_stations: Mapping[str, str]
) -> tuple[str, str] | None:
    recap_text = f"{recap.subject}\n{recap.body}".casefold()
    for team_name, station_name in team_stations.items():
        aliases = TEAM_NARRATION_ALIASES.get(team_name, ())
        recognized_names = (team_name, *aliases)
        if any(name.casefold() in recap_text for name in recognized_names):
            return team_name, station_name
    return None


def format_recap_narration(
    recap: GameRecap,
    team_stations: Mapping[str, str] = TEAM_RADIO_STATIONS,
) -> str:
    """Create a deterministic spoken introduction and recap."""
    mapped_team = _find_mapped_team(recap, team_stations)
    if mapped_team is None:
        introduction = "Your OOTP postgame report."
    else:
        team_name, station_name = mapped_team
        introduction = (
            f"This is {station_name}. Your {team_name} postgame report."
        )

    subject = _finish_sentence(recap.subject)
    return f"{introduction} {subject}\n\n{recap.body}"


def format_score_sentence(result: GameResult) -> str:
    """Create one neutral deterministic score sentence with team articles."""
    if result.away_score == result.home_score:
        return (
            f"The {result.away_team} and the {result.home_team} finished tied, "
            f"{result.away_score} to {result.home_score}."
        )
    if result.away_score > result.home_score:
        winner, winner_score = result.away_team, result.away_score
        loser, loser_score = result.home_team, result.home_score
    else:
        winner, winner_score = result.home_team, result.home_score
        loser, loser_score = result.away_team, result.away_score
    return (
        f"The {winner} defeated the {loser}, {winner_score} to {loser_score}."
    )


def format_around_league_narration(
    results: Sequence[GameResult],
    *,
    played_game_id: int,
) -> str:
    """Format other same-slate games, excluding the already recapped result."""
    other_results = [
        result for result in results if result.game_id != played_game_id
    ]
    if not other_results:
        return ""
    score_sentences = " ".join(
        format_score_sentence(result) for result in other_results
    )
    return f"Now, around the league. {score_sentences}"


def append_around_league_narration(
    recap_narration: str,
    results: Sequence[GameResult],
    *,
    played_game_id: int,
) -> str:
    """Append a separate score segment when other results are available."""
    score_segment = format_around_league_narration(
        results,
        played_game_id=played_game_id,
    )
    if not score_segment:
        return recap_narration
    return f"{recap_narration}\n\n{score_segment}"

"""Build narration text from cleaned OOTP data."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ootp_radio.models import GameRecap

TEAM_RADIO_STATIONS: Mapping[str, str] = MappingProxyType(
    {
        "Baltimore Orioles": "WBAL News Radio",
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
        if team_name.casefold() in recap_text:
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


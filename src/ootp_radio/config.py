"""Application configuration loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Configuration needed by the current command."""

    save_dir: Path
    team_name: str | None = None


def load_config(
    *, save_dir: Path | str, team_name: str | None = None
) -> AppConfig:
    """Build configuration from an explicitly selected OOTP save directory."""
    return AppConfig(save_dir=Path(save_dir).expanduser(), team_name=team_name)

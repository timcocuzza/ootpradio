"""Application configuration loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Configuration needed by the current command."""

    save_dir: Path


def load_config(*, save_dir: Path | str) -> AppConfig:
    """Build configuration from an explicitly selected OOTP save directory."""
    return AppConfig(save_dir=Path(save_dir).expanduser())


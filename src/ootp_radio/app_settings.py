"""Persisted desktop settings and pure broadcast-order operations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ootp_radio.broadcast import (
    BroadcastConfigurationError,
    normalize_segment_order,
)
from ootp_radio.models import BroadcastSegment

SETTINGS_VERSION = 1
DEFAULT_TEAM_NAME = "Baltimore Orioles"
DEFAULT_SEGMENTS = (
    BroadcastSegment.HIGHLIGHTS,
    BroadcastSegment.TEAM_RECAP,
    BroadcastSegment.SCORES,
    BroadcastSegment.NEWS,
)


class SettingsError(RuntimeError):
    """Raised when desktop settings cannot be loaded, validated, or saved."""


def default_settings_path() -> Path:
    """Return the user-owned macOS settings path outside every OOTP save."""
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "OOTP Radio"
        / "settings.json"
    )


def _optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SettingsError(f"{field_name} must be text or null.")
    stripped = value.strip()
    return stripped or None


def _optional_positive_integer(value: Any, *, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SettingsError(f"{field_name} must be a positive whole number.")
    return value


def _positive_number(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SettingsError(f"{field_name} must be a positive number.")
    parsed = float(value)
    if parsed <= 0:
        raise SettingsError(f"{field_name} must be a positive number.")
    return parsed


def _segments_from_json(value: Any) -> tuple[BroadcastSegment, ...]:
    if not isinstance(value, list):
        raise SettingsError("segments must be a list.")
    try:
        segments = tuple(BroadcastSegment(item) for item in value)
    except (TypeError, ValueError) as error:
        raise SettingsError("segments contains an unknown broadcast option.") from error
    try:
        return normalize_segment_order(segments)
    except BroadcastConfigurationError as error:
        raise SettingsError(str(error)) from error


@dataclass(frozen=True)
class AppSettings:
    """All user-configurable values needed to start desktop listening."""

    save_dir: Path | None = None
    team_name: str = DEFAULT_TEAM_NAME
    team_id: int | None = None
    voice: str | None = None
    rate: int | None = None
    segments: tuple[BroadcastSegment, ...] = DEFAULT_SEGMENTS
    off_day_broadcasts: bool = True
    play_current: bool = False
    poll_interval_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.save_dir is not None and not isinstance(self.save_dir, Path):
            object.__setattr__(self, "save_dir", Path(self.save_dir))
        if not self.team_name.strip():
            raise SettingsError("Team name cannot be empty.")
        if (
            self.team_id is not None
            and (
                isinstance(self.team_id, bool)
                or not isinstance(self.team_id, int)
                or self.team_id <= 0
            )
        ):
            raise SettingsError("Team ID must be a positive whole number.")
        if self.voice is not None and not self.voice.strip():
            object.__setattr__(self, "voice", None)
        if self.rate is not None and self.rate <= 0:
            raise SettingsError("Speech rate must be a positive whole number.")
        try:
            normalized = normalize_segment_order(self.segments)
        except BroadcastConfigurationError as error:
            raise SettingsError(str(error)) from error
        object.__setattr__(self, "segments", normalized)
        if self.poll_interval_seconds <= 0:
            raise SettingsError("Poll interval must be greater than zero.")

    @classmethod
    def from_json(cls, value: Any) -> AppSettings:
        """Validate a decoded settings object with backward-compatible defaults."""
        if not isinstance(value, dict):
            raise SettingsError("Settings must contain a JSON object.")
        version = value.get("version", SETTINGS_VERSION)
        if version != SETTINGS_VERSION:
            raise SettingsError(
                f"Unsupported settings version {version!r}; expected "
                f"{SETTINGS_VERSION}."
            )

        save_dir_text = _optional_string(
            value.get("save_dir"),
            field_name="save_dir",
        )
        team_name = value.get("team_name", DEFAULT_TEAM_NAME)
        if not isinstance(team_name, str) or not team_name.strip():
            raise SettingsError("team_name must be non-empty text.")
        voice = _optional_string(value.get("voice"), field_name="voice")
        team_id = _optional_positive_integer(
            value.get("team_id"),
            field_name="team_id",
        )
        rate = _optional_positive_integer(value.get("rate"), field_name="rate")
        segments = _segments_from_json(
            value.get(
                "segments",
                [segment.value for segment in DEFAULT_SEGMENTS],
            )
        )
        off_day_broadcasts = value.get("off_day_broadcasts", True)
        play_current = value.get("play_current", False)
        if not isinstance(off_day_broadcasts, bool):
            raise SettingsError("off_day_broadcasts must be true or false.")
        if not isinstance(play_current, bool):
            raise SettingsError("play_current must be true or false.")
        poll_interval = _positive_number(
            value.get("poll_interval_seconds", 2.0),
            field_name="poll_interval_seconds",
        )

        return cls(
            save_dir=Path(save_dir_text).expanduser() if save_dir_text else None,
            team_name=team_name.strip(),
            team_id=team_id,
            voice=voice,
            rate=rate,
            segments=segments,
            off_day_broadcasts=off_day_broadcasts,
            play_current=play_current,
            poll_interval_seconds=poll_interval,
        )

    def to_json(self) -> dict[str, Any]:
        """Return stable JSON-compatible settings data."""
        return {
            "version": SETTINGS_VERSION,
            "save_dir": str(self.save_dir) if self.save_dir is not None else None,
            "team_name": self.team_name,
            "team_id": self.team_id,
            "voice": self.voice,
            "rate": self.rate,
            "segments": [segment.value for segment in self.segments],
            "off_day_broadcasts": self.off_day_broadcasts,
            "play_current": self.play_current,
            "poll_interval_seconds": self.poll_interval_seconds,
        }


def load_settings(path: Path | str | None = None) -> AppSettings:
    """Load settings, returning defaults only when the file does not exist."""
    settings_path = Path(path) if path is not None else default_settings_path()
    try:
        document = settings_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AppSettings()
    except OSError as error:
        raise SettingsError(
            f"Could not read settings '{settings_path}': {error}."
        ) from error
    try:
        decoded = json.loads(document)
    except json.JSONDecodeError as error:
        raise SettingsError(
            f"Settings file '{settings_path}' is not valid JSON."
        ) from error
    return AppSettings.from_json(decoded)


def save_settings(
    settings: AppSettings,
    path: Path | str | None = None,
) -> Path:
    """Atomically persist settings without ever writing inside an OOTP save."""
    settings_path = Path(path) if path is not None else default_settings_path()
    temporary_path = settings_path.with_name(f".{settings_path.name}.tmp")
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(
            json.dumps(settings.to_json(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, settings_path)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise SettingsError(
            f"Could not save settings '{settings_path}': {error}."
        ) from error
    return settings_path


def set_segment_enabled(
    order: tuple[BroadcastSegment, ...],
    segment: BroadcastSegment,
    *,
    enabled: bool,
) -> tuple[BroadcastSegment, ...]:
    """Add/remove one segment while preserving News-last and one selection."""
    current = normalize_segment_order(order)
    if enabled:
        if segment in current:
            return current
        return normalize_segment_order((*current, segment))
    if segment not in current:
        return current
    remaining = tuple(item for item in current if item is not segment)
    if not remaining:
        raise SettingsError("At least one broadcast option must stay enabled.")
    return normalize_segment_order(remaining)


def move_segment(
    order: tuple[BroadcastSegment, ...],
    *,
    source_index: int,
    target_index: int,
) -> tuple[BroadcastSegment, ...]:
    """Move a selected segment while treating News as an immovable footer."""
    current = list(normalize_segment_order(order))
    if not (0 <= source_index < len(current)):
        raise SettingsError("Drag source is outside the broadcast order.")
    if not (0 <= target_index < len(current)):
        raise SettingsError("Drag destination is outside the broadcast order.")
    if current[source_index] is BroadcastSegment.NEWS:
        return tuple(current)

    moved = current.pop(source_index)
    news_index = (
        current.index(BroadcastSegment.NEWS)
        if BroadcastSegment.NEWS in current
        else len(current)
    )
    current.insert(min(target_index, news_index), moved)
    return normalize_segment_order(current)

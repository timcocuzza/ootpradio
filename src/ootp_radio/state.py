"""Persistent watcher state stored outside the OOTP save."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class StateError(RuntimeError):
    """Raised when watcher state cannot be loaded or saved safely."""


@dataclass(frozen=True)
class WatchState:
    """Durable duplicate-prevention state."""

    last_processed_game_id: int | None = None
    last_processed_at: str | None = None
    baseline_game_id: int | None = None

    def already_handled(self, game_id: int) -> bool:
        """Return whether a game was narrated or deliberately baselined."""
        return game_id in {self.last_processed_game_id, self.baseline_game_id}


def _optional_game_id(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise StateError(f"State field '{field_name}' must be a nonnegative integer.")
    return value


def load_state(path: Path | str) -> WatchState:
    """Load state, returning an empty state when the file does not exist."""
    state_path = Path(path)
    try:
        document = state_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return WatchState()
    except OSError as error:
        raise StateError(f"Could not read state file '{state_path}': {error}.") from error

    try:
        data = json.loads(document)
    except json.JSONDecodeError as error:
        raise StateError(
            f"State file '{state_path}' is not valid JSON: {error.msg}."
        ) from error

    if not isinstance(data, dict):
        raise StateError(f"State file '{state_path}' must contain a JSON object.")

    processed_at = data.get("last_processed_at")
    if processed_at is not None and not isinstance(processed_at, str):
        raise StateError("State field 'last_processed_at' must be a string or null.")

    return WatchState(
        last_processed_game_id=_optional_game_id(
            data.get("last_processed_game_id"), "last_processed_game_id"
        ),
        last_processed_at=processed_at,
        baseline_game_id=_optional_game_id(
            data.get("baseline_game_id"), "baseline_game_id"
        ),
    )


def save_state(path: Path | str, state: WatchState) -> None:
    """Atomically replace the state file using a temporary sibling file."""
    state_path = Path(path)
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=state_path.parent,
            prefix=f".{state_path.name}.",
            suffix=".tmp",
        )
    except OSError as error:
        raise StateError(f"Could not prepare state file '{state_path}': {error}.") from error

    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(asdict(state), temporary_file, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, state_path)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise StateError(f"Could not save state file '{state_path}': {error}.") from error


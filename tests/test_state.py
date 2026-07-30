"""Tests for persistent atomic watcher state."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ootp_radio.state import StateError, WatchState, load_state, save_state


def test_missing_state_file_loads_empty_state(tmp_path: Path) -> None:
    assert load_state(tmp_path / "missing.json") == WatchState()


def test_state_round_trip_preserves_duplicate_prevention_fields(tmp_path: Path) -> None:
    state_path = tmp_path / "var" / "state.json"
    state = WatchState(
        last_processed_game_id=1600,
        last_processed_at="2032-08-02T12:00:00+00:00",
        baseline_game_id=1596,
    )

    save_state(state_path, state)

    assert load_state(state_path) == state


def test_corrupted_state_file_has_a_clear_error(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(StateError, match="is not valid JSON"):
        load_state(state_path)


def test_state_file_must_contain_an_object(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps([1596]), encoding="utf-8")

    with pytest.raises(StateError, match="must contain a JSON object"):
        load_state(state_path)


def test_state_save_uses_atomic_replace(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"

    with patch("ootp_radio.state.os.replace", wraps=os.replace) as replace:
        save_state(state_path, WatchState(last_processed_game_id=1596))

    replace.assert_called_once()
    assert load_state(state_path).last_processed_game_id == 1596

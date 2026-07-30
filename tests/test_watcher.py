"""Tests for automatic polling and duplicate prevention."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from ootp_radio.box_score_parser import ScoreSlateNotReadyError
from ootp_radio.models import GameResult
from ootp_radio.speech import SpeechError
from ootp_radio.state import StateError, load_state
from ootp_radio.watcher import RecapWatcher

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "game_1596" / "game_box_1596.html"
)


class RecordingSpeaker:
    def __init__(self) -> None:
        self.narrations: list[str] = []

    def speak(self, narration: str) -> None:
        self.narrations.append(narration)


class FailingSpeaker(RecordingSpeaker):
    def speak(self, narration: str) -> None:
        self.narrations.append(narration)
        raise SpeechError("test speech failure")


def _create_save_dir(tmp_path: Path) -> Path:
    save_dir = tmp_path / "Watched League.lg"
    (save_dir / "replays").mkdir(parents=True)
    (save_dir / "news" / "html" / "box_scores").mkdir(parents=True)
    return save_dir


def _add_game(save_dir: Path, game_id: int, *, valid_recap: bool = True) -> None:
    (save_dir / "replays" / f"replay_{game_id}.rpl").write_bytes(b"replay")
    box_score = (
        save_dir / "news" / "html" / "box_scores" / f"game_box_{game_id}.html"
    )
    if valid_recap:
        document = FIXTURE_PATH.read_text(encoding="utf-8").replace(
            "game_box_1596", f"game_box_{game_id}"
        )
    else:
        document = "<html>No recap markers</html>"
    box_score.write_text(document, encoding="utf-8")


def _watcher(
    save_dir: Path,
    state_file: Path,
    speaker: RecordingSpeaker,
    **kwargs,
) -> RecapWatcher:
    return RecapWatcher(
        save_dir=save_dir,
        state_file=state_file,
        speaker=speaker,
        poll_interval_seconds=1.0,
        sleep=kwargs.pop("sleep", lambda _: None),
        now=lambda: datetime(2032, 8, 2, 12, 0, tzinfo=timezone.utc),
        **kwargs,
    )


def test_starting_watcher_baselines_current_game_without_speaking(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596)
    state_file = tmp_path / "var" / "state.json"
    speaker = RecordingSpeaker()

    _watcher(save_dir, state_file, speaker).run(max_polls=1)

    state = load_state(state_file)
    assert speaker.narrations == []
    assert state.baseline_game_id == 1596
    assert state.last_processed_game_id is None


def test_play_current_speaks_and_marks_game_processed(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596)
    state_file = tmp_path / "var" / "state.json"
    speaker = RecordingSpeaker()

    _watcher(save_dir, state_file, speaker, play_current=True).run(max_polls=1)

    state = load_state(state_file)
    assert len(speaker.narrations) == 1
    assert state.last_processed_game_id == 1596
    assert state.last_processed_at == "2032-08-02T12:00:00+00:00"


def test_new_game_is_spoken_exactly_once_across_multiple_polls(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596)
    state_file = tmp_path / "var" / "state.json"
    speaker = RecordingSpeaker()
    new_game_added = False

    def add_game_during_poll(seconds: float) -> None:
        nonlocal new_game_added
        if seconds == 1.0 and not new_game_added:
            _add_game(save_dir, 1600)
            new_game_added = True

    _watcher(
        save_dir,
        state_file,
        speaker,
        sleep=add_game_during_poll,
    ).run(max_polls=3)

    assert len(speaker.narrations) == 1
    assert load_state(state_file).last_processed_game_id == 1600


def test_restart_does_not_repeat_processed_game(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596)
    state_file = tmp_path / "var" / "state.json"
    first_speaker = RecordingSpeaker()
    second_speaker = RecordingSpeaker()
    _watcher(save_dir, state_file, first_speaker, play_current=True).run(max_polls=1)

    _watcher(save_dir, state_file, second_speaker).run(max_polls=1)

    assert len(first_speaker.narrations) == 1
    assert second_speaker.narrations == []


def test_parse_failure_does_not_mark_game_processed(
    tmp_path: Path, caplog
) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596, valid_recap=False)
    state_file = tmp_path / "var" / "state.json"
    speaker = RecordingSpeaker()

    _watcher(save_dir, state_file, speaker, play_current=True).run(max_polls=1)

    assert speaker.narrations == []
    assert load_state(state_file).last_processed_game_id is None
    assert "recap_failed" in caplog.text


def test_speech_failure_does_not_mark_game_processed(
    tmp_path: Path, caplog
) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596)
    state_file = tmp_path / "var" / "state.json"
    speaker = FailingSpeaker()

    _watcher(save_dir, state_file, speaker, play_current=True).run(max_polls=1)

    assert len(speaker.narrations) == 1
    assert load_state(state_file).last_processed_game_id is None
    assert "speech_failed" in caplog.text


def test_state_file_inside_save_is_rejected(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    speaker = RecordingSpeaker()
    watcher = _watcher(save_dir, save_dir / "state.json", speaker)

    with pytest.raises(StateError, match="must be outside the OOTP save"):
        watcher.run(max_polls=1)


def test_watcher_can_speak_other_scores_after_recap(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596)
    state_file = tmp_path / "var" / "state.json"
    speaker = RecordingSpeaker()
    results = [
        GameResult(1596, None, "Baltimore Orioles", 7, "Detroit Tigers", 4),
        GameResult(1600, None, "Seattle Mariners", 10, "Texas Rangers", 3),
    ]

    with patch(
        "ootp_radio.live_recap.discover_same_slate_results", return_value=results
    ):
        _watcher(
            save_dir,
            state_file,
            speaker,
            play_current=True,
            include_around_league=True,
        ).run(max_polls=1)

    assert len(speaker.narrations) == 1
    assert "Now, around the league." in speaker.narrations[0]
    assert "The Seattle Mariners defeated the Texas Rangers" in speaker.narrations[0]
    assert "The Baltimore Orioles defeated the Detroit Tigers" not in speaker.narrations[0]


def test_score_failure_falls_back_to_recap_and_marks_processed(
    tmp_path: Path, caplog
) -> None:
    save_dir = _create_save_dir(tmp_path)
    _add_game(save_dir, 1596)
    state_file = tmp_path / "var" / "state.json"
    speaker = RecordingSpeaker()

    with patch(
        "ootp_radio.watcher.add_around_league",
        side_effect=ScoreSlateNotReadyError("scores still changing"),
    ):
        _watcher(
            save_dir,
            state_file,
            speaker,
            play_current=True,
            include_around_league=True,
        ).run(max_polls=1)

    assert len(speaker.narrations) == 1
    assert "Now, around the league." not in speaker.narrations[0]
    assert load_state(state_file).last_processed_game_id == 1596
    assert "around_league_failed" in caplog.text

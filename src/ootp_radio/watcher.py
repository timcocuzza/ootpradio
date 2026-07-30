"""Polling watcher for automatic latest-game recap narration."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from ootp_radio.game_detector import (
    GameDetectionError,
    GameNotReadyError,
    NoReplayFilesError,
    detect_latest_game,
    ensure_game_files_stable,
)
from ootp_radio.live_recap import prepare_game_recap
from ootp_radio.paths import require_valid_save_dir
from ootp_radio.recap_parser import RecapParseError
from ootp_radio.speech import MacSaySpeaker, SpeechError
from ootp_radio.state import StateError, WatchState, load_state, save_state

_LOGGER = logging.getLogger("ootp_radio.watcher")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecapWatcher:
    """Poll a save and narrate each newly completed played game once."""

    def __init__(
        self,
        *,
        save_dir: Path | str,
        state_file: Path | str,
        speaker: MacSaySpeaker,
        poll_interval_seconds: float = 2.0,
        play_current: bool = False,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")

        self.save_dir = Path(save_dir)
        self.state_file = Path(state_file)
        self.speaker = speaker
        self.poll_interval_seconds = poll_interval_seconds
        self.play_current = play_current
        self.sleep = sleep
        self.now = now

    def _ensure_state_outside_save(self) -> None:
        save_path = self.save_dir.resolve()
        state_path = self.state_file.resolve()
        if state_path == save_path or state_path.is_relative_to(save_path):
            raise StateError(
                f"State file '{self.state_file}' must be outside the OOTP save "
                "directory. Choose a path such as ./var/state.json."
            )

    def _try_baseline(self, state: WatchState) -> tuple[WatchState, bool]:
        try:
            game_files = detect_latest_game(self.save_dir)
            ensure_game_files_stable(game_files, sleep=self.sleep)
        except NoReplayFilesError:
            _LOGGER.info("baseline_empty no_replays=true")
            return state, False
        except GameNotReadyError as error:
            _LOGGER.info('baseline_waiting reason="%s"', error)
            return state, True
        except GameDetectionError as error:
            _LOGGER.error('baseline_failed reason="%s"', error)
            return state, True

        baselined_state = replace(state, baseline_game_id=game_files.game_id)
        save_state(self.state_file, baselined_state)
        _LOGGER.info("watcher_baselined game_id=%s", game_files.game_id)
        return baselined_state, False

    def _try_process_latest(
        self, state: WatchState, *, force: bool = False
    ) -> tuple[WatchState, bool]:
        try:
            game_files = detect_latest_game(self.save_dir)
        except NoReplayFilesError:
            _LOGGER.info("waiting_for_replay no_replays=true")
            return state, False
        except GameNotReadyError as error:
            _LOGGER.info('waiting_for_game reason="%s"', error)
            return state, False
        except GameDetectionError as error:
            _LOGGER.error('game_detection_failed reason="%s"', error)
            return state, False

        if not force and state.already_handled(game_files.game_id):
            return state, False

        _LOGGER.info("replay_detected game_id=%s", game_files.game_id)
        try:
            prepared = prepare_game_recap(game_files, sleep=self.sleep)
        except GameNotReadyError as error:
            _LOGGER.info(
                'waiting_for_stable_file game_id=%s reason="%s"',
                game_files.game_id,
                error,
            )
            return state, False
        except (GameDetectionError, RecapParseError) as error:
            _LOGGER.error(
                'recap_failed game_id=%s reason="%s"', game_files.game_id, error
            )
            return state, False

        _LOGGER.info("speech_started game_id=%s mode=recap", game_files.game_id)
        try:
            self.speaker.speak(prepared.narration_text)
        except SpeechError as error:
            _LOGGER.error(
                'speech_failed game_id=%s reason="%s"', game_files.game_id, error
            )
            return state, False

        processed_state = replace(
            state,
            last_processed_game_id=game_files.game_id,
            last_processed_at=self.now().astimezone(timezone.utc).isoformat(),
        )
        save_state(self.state_file, processed_state)
        _LOGGER.info("game_marked_processed game_id=%s", game_files.game_id)
        return processed_state, True

    def run(self, *, max_polls: int | None = None) -> None:
        """Run until interrupted; ``max_polls`` exists for deterministic tests."""
        if max_polls is not None and max_polls < 1:
            return

        require_valid_save_dir(self.save_dir)
        self._ensure_state_outside_save()
        state = load_state(self.state_file)
        baseline_pending = (
            not self.play_current
            and state.last_processed_game_id is None
            and state.baseline_game_id is None
        )
        force_current_pending = self.play_current
        poll_count = 0

        _LOGGER.info(
            'watcher_started save_dir="%s" state_file="%s" poll_interval=%s',
            self.save_dir,
            self.state_file,
            self.poll_interval_seconds,
        )

        while True:
            if baseline_pending:
                state, baseline_pending = self._try_baseline(state)
            else:
                state, processed = self._try_process_latest(
                    state, force=force_current_pending
                )
                if processed:
                    force_current_pending = False

            poll_count += 1
            if max_polls is not None and poll_count >= max_polls:
                return
            self.sleep(self.poll_interval_seconds)


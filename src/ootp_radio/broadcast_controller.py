"""Latest-wins broadcast monitoring with cancellable macOS speech."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Protocol

from ootp_radio.box_score_parser import BoxScoreError
from ootp_radio.broadcast import (
    BroadcastError,
    iter_game_broadcast_parts,
    normalize_segment_order,
)
from ootp_radio.game_detector import (
    GameDetectionError,
    GameNotReadyError,
    NoReplayFilesError,
    detect_latest_game,
    ensure_game_files_stable,
)
from ootp_radio.message_parser import MessageError
from ootp_radio.models import (
    BroadcastIssue,
    BroadcastSection,
    BroadcastSegment,
    GameFiles,
)
from ootp_radio.recap_parser import RecapParseError
from ootp_radio.replay_strings import HighlightError
from ootp_radio.speech import CancellableMacSaySpeaker, SpeechError

_LOGGER = logging.getLogger("ootp_radio.broadcast_controller")
BroadcastPart = BroadcastSection | BroadcastIssue


class _CancellableSpeaker(Protocol):
    def speak(
        self,
        text: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> bool: ...

    def stop(self) -> bool: ...


class LatestWinsBroadcastController:
    """Interrupt obsolete audio and retain only the newest detected game."""

    def __init__(
        self,
        *,
        save_dir: Path | str,
        team_name: str,
        segments: Sequence[BroadcastSegment],
        speaker: _CancellableSpeaker,
        poll_interval_seconds: float = 2.0,
        play_current: bool = False,
        detector: Callable[[Path | str], GameFiles] = detect_latest_game,
        stabilizer: Callable[[GameFiles], None] = ensure_game_files_stable,
        part_factory: Callable[
            [GameFiles], Iterable[BroadcastPart]
        ] | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")
        if not team_name.strip():
            raise ValueError("team_name cannot be empty")

        self.save_dir = Path(save_dir)
        self.team_name = team_name
        self.segments = normalize_segment_order(segments)
        self.speaker = speaker
        self.poll_interval_seconds = poll_interval_seconds
        self.play_current = play_current
        self.detector = detector
        self.stabilizer = stabilizer
        self.part_factory = part_factory or self._default_part_factory

        self._condition = threading.Condition()
        self._cancel_playback = threading.Event()
        self._shutdown = threading.Event()
        self._initialized = False
        self._recognized_game_id: int | None = None
        self._pending_game: GameFiles | None = None
        self._active_game: GameFiles | None = None

    def _default_part_factory(
        self, game_files: GameFiles
    ) -> Iterable[BroadcastPart]:
        return iter_game_broadcast_parts(
            game_files,
            team_name=self.team_name,
            segments=self.segments,
        )

    @property
    def active_game_id(self) -> int | None:
        with self._condition:
            return (
                self._active_game.game_id
                if self._active_game is not None
                else None
            )

    @property
    def pending_game_id(self) -> int | None:
        with self._condition:
            return (
                self._pending_game.game_id
                if self._pending_game is not None
                else None
            )

    @property
    def recognized_game_id(self) -> int | None:
        with self._condition:
            return self._recognized_game_id

    def _detect_stable_latest(self) -> GameFiles | None:
        try:
            game_files = self.detector(self.save_dir)
            self.stabilizer(game_files)
            return game_files
        except NoReplayFilesError:
            return None
        except GameNotReadyError as error:
            _LOGGER.info('new_game_not_stable reason="%s"', error)
            return None
        except GameDetectionError as error:
            _LOGGER.error('new_game_detection_failed reason="%s"', error)
            return None

    def initialize(self) -> None:
        """Baseline the current game, optionally scheduling it for playback."""
        with self._condition:
            if self._initialized:
                return
        game_files = self._detect_stable_latest()
        with self._condition:
            if self._initialized:
                return
            self._initialized = True
            if game_files is not None:
                self._recognized_game_id = game_files.game_id
                if self.play_current:
                    self._pending_game = game_files
                    self._condition.notify_all()

    def recognize_game(self, game_files: GameFiles) -> bool:
        """Replace pending work and interrupt audio for an obsolete game."""
        with self._condition:
            if self._recognized_game_id == game_files.game_id:
                return False
            self._recognized_game_id = game_files.game_id
            self._pending_game = game_files
            should_interrupt = (
                self._active_game is not None
                and self._active_game.game_id != game_files.game_id
            )
            if should_interrupt:
                self._cancel_playback.set()
            self._condition.notify_all()

        if should_interrupt:
            self.speaker.stop()
            _LOGGER.info(
                "obsolete_playback_stopped new_game_id=%s", game_files.game_id
            )
        return True

    def poll_once(self) -> bool:
        """Recognize one stable latest game without queuing intermediates."""
        if not self._initialized:
            self.initialize()
            return False
        game_files = self._detect_stable_latest()
        if game_files is None:
            return False
        return self.recognize_game(game_files)

    def stop_playback(self) -> bool:
        """Discard current audio while monitoring remains active."""
        with self._condition:
            if self._active_game is None:
                return False
            self._cancel_playback.set()
        self.speaker.stop()
        return True

    def stop_listening(self) -> None:
        """Stop monitoring, discard pending work, and terminate active audio."""
        self._shutdown.set()
        with self._condition:
            self._pending_game = None
            self._cancel_playback.set()
            self._condition.notify_all()
        self.speaker.stop()

    def play_pending_once(self) -> bool | None:
        """Play the newest pending game; return ``None`` when there is none."""
        with self._condition:
            if self._pending_game is None:
                return None
            game_files = self._pending_game
            self._pending_game = None
            self._cancel_playback.clear()
            self._active_game = game_files

        completed = True
        try:
            for part in self.part_factory(game_files):
                if self._cancel_playback.is_set():
                    completed = False
                    break
                if isinstance(part, BroadcastIssue):
                    _LOGGER.warning(
                        'segment_skipped game_id=%s segment=%s reason="%s"',
                        game_files.game_id,
                        part.segment.value,
                        part.reason,
                    )
                    continue
                for chunk in part.chunks:
                    if self._cancel_playback.is_set() or not self.speaker.speak(
                        chunk,
                        cancel_event=self._cancel_playback,
                    ):
                        completed = False
                        break
                if not completed:
                    break
        except (
            BoxScoreError,
            BroadcastError,
            GameDetectionError,
            HighlightError,
            MessageError,
            RecapParseError,
            SpeechError,
        ) as error:
            completed = False
            _LOGGER.error(
                'broadcast_failed game_id=%s reason="%s"',
                game_files.game_id,
                error,
            )
        finally:
            with self._condition:
                if self._active_game is game_files:
                    self._active_game = None
                self._condition.notify_all()

        return completed

    def _monitor(self) -> None:
        while not self._shutdown.is_set():
            self.poll_once()
            self._shutdown.wait(self.poll_interval_seconds)

    def run(self) -> None:
        """Monitor in the background while playing newest work in this thread."""
        self.initialize()
        monitor = threading.Thread(
            target=self._monitor,
            name="ootp-radio-monitor",
            daemon=True,
        )
        monitor.start()
        try:
            while not self._shutdown.is_set():
                result = self.play_pending_once()
                if result is None:
                    with self._condition:
                        self._condition.wait(timeout=self.poll_interval_seconds)
        finally:
            self.stop_listening()
            monitor.join(timeout=max(1.0, self.poll_interval_seconds * 2))


def build_latest_wins_controller(
    *,
    save_dir: Path | str,
    team_name: str,
    segments: Sequence[BroadcastSegment],
    voice: str | None = None,
    rate: int | None = None,
    poll_interval_seconds: float = 2.0,
    play_current: bool = False,
) -> LatestWinsBroadcastController:
    """Build the production controller with controllable macOS speech."""
    return LatestWinsBroadcastController(
        save_dir=save_dir,
        team_name=team_name,
        segments=segments,
        speaker=CancellableMacSaySpeaker(voice=voice, rate=rate),
        poll_interval_seconds=poll_interval_seconds,
        play_current=play_current,
    )

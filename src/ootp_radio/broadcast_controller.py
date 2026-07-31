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
    iter_off_day_broadcast_parts,
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
    GameDayEvent,
    GameFiles,
    OffDayEvent,
)
from ootp_radio.radio_event import (
    LatestRadioEventDetector,
    RadioEvent,
    RadioEventError,
    RadioEventNotReadyError,
)
from ootp_radio.recap_parser import RecapParseError
from ootp_radio.replay_strings import HighlightError
from ootp_radio.speech import CancellableMacSaySpeaker, SpeechError

_LOGGER = logging.getLogger("ootp_radio.broadcast_controller")
BroadcastPart = BroadcastSection | BroadcastIssue
BroadcastTarget = GameFiles | GameDayEvent | OffDayEvent


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
        event_detector: Callable[[], RadioEvent] | None = None,
        include_off_days: bool = True,
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
        self._custom_part_factory = part_factory
        self.part_factory = part_factory or self._default_part_factory
        self.event_detector = event_detector
        self.include_off_days = include_off_days

        self._condition = threading.Condition()
        self._cancel_playback = threading.Event()
        self._shutdown = threading.Event()
        self._initialized = False
        self._recognized_key: str | None = None
        self._recognized_game_id: int | None = None
        self._pending_target: BroadcastTarget | None = None
        self._active_target: BroadcastTarget | None = None

    def _default_part_factory(
        self, target: BroadcastTarget
    ) -> Iterable[BroadcastPart]:
        if isinstance(target, OffDayEvent):
            if not self.include_off_days:
                return ()
            return iter_off_day_broadcast_parts(
                target.slate,
                save_dir=self.save_dir,
                team_name=self.team_name,
                segments=self.segments,
            )
        game_files = (
            target.game_files if isinstance(target, GameDayEvent) else target
        )
        return iter_game_broadcast_parts(
            game_files,
            team_name=self.team_name,
            segments=self.segments,
        )

    @staticmethod
    def _target_key(target: BroadcastTarget) -> str:
        if isinstance(target, GameFiles):
            return f"game:{target.game_id}"
        return target.key

    @staticmethod
    def _target_game_id(target: BroadcastTarget | None) -> int | None:
        if isinstance(target, GameFiles):
            return target.game_id
        if isinstance(target, GameDayEvent):
            return target.game_files.game_id
        return None

    def _parts_for_target(
        self, target: BroadcastTarget
    ) -> Iterable[BroadcastPart]:
        if self._custom_part_factory is None:
            return self._default_part_factory(target)
        if isinstance(target, GameDayEvent):
            return self.part_factory(target.game_files)
        return self.part_factory(target)  # type: ignore[arg-type]

    @property
    def active_game_id(self) -> int | None:
        with self._condition:
            return self._target_game_id(self._active_target)

    @property
    def pending_game_id(self) -> int | None:
        with self._condition:
            return self._target_game_id(self._pending_target)

    @property
    def active_event_key(self) -> str | None:
        with self._condition:
            if self._active_target is None:
                return None
            return self._target_key(self._active_target)

    @property
    def pending_event_key(self) -> str | None:
        with self._condition:
            if self._pending_target is None:
                return None
            return self._target_key(self._pending_target)

    @property
    def recognized_event_key(self) -> str | None:
        with self._condition:
            return self._recognized_key

    @property
    def recognized_game_id(self) -> int | None:
        with self._condition:
            return self._recognized_game_id

    def _detect_stable_latest(self) -> BroadcastTarget | None:
        if self.event_detector is not None:
            try:
                return self.event_detector()
            except RadioEventNotReadyError as error:
                _LOGGER.info('radio_event_not_stable reason="%s"', error)
                return None
            except (RadioEventError, BoxScoreError) as error:
                _LOGGER.error('radio_event_detection_failed reason="%s"', error)
                return None
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
        target = self._detect_stable_latest()
        with self._condition:
            if self._initialized:
                return
            self._initialized = True
            if target is not None:
                self._recognized_key = self._target_key(target)
                self._recognized_game_id = self._target_game_id(target)
                if self.play_current:
                    self._pending_target = target
                    self._condition.notify_all()

    def recognize_game(self, game_files: GameFiles) -> bool:
        """Replace pending work and interrupt audio for an obsolete game."""
        return self.recognize_event(game_files)

    def recognize_event(self, target: BroadcastTarget) -> bool:
        """Replace pending work and interrupt audio for an obsolete event."""
        target_key = self._target_key(target)
        with self._condition:
            if self._recognized_key == target_key:
                return False
            self._recognized_key = target_key
            self._recognized_game_id = self._target_game_id(target)
            self._pending_target = target
            should_interrupt = (
                self._active_target is not None
                and self._target_key(self._active_target) != target_key
            )
            if should_interrupt:
                self._cancel_playback.set()
            self._condition.notify_all()

        if should_interrupt:
            self.speaker.stop()
            _LOGGER.info(
                "obsolete_playback_stopped new_event=%s", target_key
            )
        return True

    def poll_once(self) -> bool:
        """Recognize one stable latest game without queuing intermediates."""
        if not self._initialized:
            self.initialize()
            return False
        target = self._detect_stable_latest()
        if target is None:
            return False
        return self.recognize_event(target)

    def stop_playback(self) -> bool:
        """Discard current audio while monitoring remains active."""
        with self._condition:
            if self._active_target is None:
                return False
            self._cancel_playback.set()
        self.speaker.stop()
        return True

    def stop_listening(self) -> None:
        """Stop monitoring, discard pending work, and terminate active audio."""
        self._shutdown.set()
        with self._condition:
            self._pending_target = None
            self._cancel_playback.set()
            self._condition.notify_all()
        self.speaker.stop()

    def play_pending_once(self) -> bool | None:
        """Play the newest pending game; return ``None`` when there is none."""
        with self._condition:
            if self._pending_target is None:
                return None
            target = self._pending_target
            target_key = self._target_key(target)
            self._pending_target = None
            self._cancel_playback.clear()
            self._active_target = target

        completed = True
        try:
            for part in self._parts_for_target(target):
                if self._cancel_playback.is_set():
                    completed = False
                    break
                if isinstance(part, BroadcastIssue):
                    _LOGGER.warning(
                        'segment_skipped event=%s segment=%s reason="%s"',
                        target_key,
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
                'broadcast_failed event=%s reason="%s"',
                target_key,
                error,
            )
        finally:
            with self._condition:
                if self._active_target is target:
                    self._active_target = None
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
    team_id: int | None = None,
    segments: Sequence[BroadcastSegment],
    voice: str | None = None,
    rate: int | None = None,
    poll_interval_seconds: float = 2.0,
    play_current: bool = False,
    include_off_days: bool = True,
) -> LatestWinsBroadcastController:
    """Build the production controller with controllable macOS speech."""
    event_detector = LatestRadioEventDetector(
        save_dir=save_dir,
        team_name=team_name,
        team_id=team_id,
    )
    return LatestWinsBroadcastController(
        save_dir=save_dir,
        team_name=team_name,
        segments=segments,
        speaker=CancellableMacSaySpeaker(voice=voice, rate=rate),
        poll_interval_seconds=poll_interval_seconds,
        play_current=play_current,
        event_detector=event_detector.detect,
        include_off_days=include_off_days,
    )

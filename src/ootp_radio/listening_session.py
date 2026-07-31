"""Thread-safe lifecycle wrapper used by the desktop listening controls."""

from __future__ import annotations

import threading
from collections.abc import Callable
from enum import StrEnum
from typing import Protocol

from ootp_radio.app_settings import AppSettings
from ootp_radio.broadcast_controller import build_latest_wins_controller
from ootp_radio.paths import require_valid_save_dir


class SessionStatus(StrEnum):
    """Small state machine presented by Start and Stop buttons."""

    STOPPED = "stopped"
    STARTING = "starting"
    LISTENING = "listening"
    STOPPING = "stopping"


class SessionError(RuntimeError):
    """Raised when a listening lifecycle action is invalid or cannot start."""


class _Controller(Protocol):
    def run(self) -> None: ...

    def stop_playback(self) -> bool: ...

    def stop_listening(self) -> None: ...


ControllerFactory = Callable[..., _Controller]
StatusCallback = Callable[[SessionStatus, Exception | None], None]


class ListeningSession:
    """Run the blocking radio controller safely outside Tk's event thread."""

    def __init__(
        self,
        *,
        controller_factory: ControllerFactory = build_latest_wins_controller,
        status_callback: StatusCallback | None = None,
    ) -> None:
        self.controller_factory = controller_factory
        self.status_callback = status_callback
        self._lock = threading.Lock()
        self._status = SessionStatus.STOPPED
        self._controller: _Controller | None = None
        self._thread: threading.Thread | None = None
        self._stop_requested = False
        self._last_error: Exception | None = None

    @property
    def status(self) -> SessionStatus:
        with self._lock:
            return self._status

    @property
    def last_error(self) -> Exception | None:
        with self._lock:
            return self._last_error

    def _notify(
        self,
        status: SessionStatus,
        error: Exception | None = None,
    ) -> None:
        if self.status_callback is not None:
            self.status_callback(status, error)

    def _set_status(
        self,
        status: SessionStatus,
        error: Exception | None = None,
    ) -> None:
        with self._lock:
            self._status = status
            if error is not None:
                self._last_error = error
        self._notify(status, error)

    def start(self, settings: AppSettings) -> None:
        """Validate settings, build one controller, and begin listening."""
        with self._lock:
            if self._status is not SessionStatus.STOPPED:
                raise SessionError("Listening is already starting or active.")
            self._status = SessionStatus.STARTING
            self._last_error = None
            self._stop_requested = False
        self._notify(SessionStatus.STARTING)

        try:
            if settings.save_dir is None:
                raise SessionError("Choose an OOTP saved-game folder first.")
            require_valid_save_dir(settings.save_dir)
            controller = self.controller_factory(
                save_dir=settings.save_dir,
                team_name=settings.team_name,
                segments=settings.segments,
                voice=settings.voice,
                rate=settings.rate,
                poll_interval_seconds=settings.poll_interval_seconds,
                play_current=settings.play_current,
                include_off_days=settings.off_day_broadcasts,
            )
        except Exception as error:
            self._set_status(SessionStatus.STOPPED, error)
            raise

        thread = threading.Thread(
            target=self._run_controller,
            args=(controller,),
            name="ootp-radio-desktop-session",
            daemon=True,
        )
        with self._lock:
            self._controller = controller
            self._thread = thread
            stop_requested = self._stop_requested
            self._status = (
                SessionStatus.STOPPING
                if stop_requested
                else SessionStatus.LISTENING
            )
        if stop_requested:
            self._notify(SessionStatus.STOPPING)
        else:
            self._notify(SessionStatus.LISTENING)
        thread.start()
        if stop_requested:
            controller.stop_listening()

    def _run_controller(self, controller: _Controller) -> None:
        error: Exception | None = None
        try:
            controller.run()
        except Exception as caught:
            error = caught
        finally:
            with self._lock:
                if self._controller is controller:
                    self._controller = None
                    self._thread = None
                    self._stop_requested = False
                    self._status = SessionStatus.STOPPED
                    if error is not None:
                        self._last_error = error
            self._notify(SessionStatus.STOPPED, error)

    def stop_playback(self) -> bool:
        """Stop current speech while leaving file monitoring active."""
        with self._lock:
            controller = self._controller
            listening = self._status is SessionStatus.LISTENING
        if controller is None or not listening:
            return False
        return controller.stop_playback()

    def stop_listening(self) -> bool:
        """Request full shutdown without blocking Tk's event thread."""
        with self._lock:
            if self._status is SessionStatus.STOPPED:
                return False
            if self._status is SessionStatus.STOPPING:
                return False
            self._status = SessionStatus.STOPPING
            self._stop_requested = True
            controller = self._controller
        self._notify(SessionStatus.STOPPING)
        if controller is not None:
            controller.stop_listening()
        return True

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for shutdown in tests or application-close cleanup."""
        with self._lock:
            thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

"""macOS text-to-speech support."""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass, field


class SpeechError(RuntimeError):
    """Raised when narration cannot be spoken."""


@dataclass(frozen=True)
class MacSaySpeaker:
    """Speak text with the macOS ``say`` command."""

    voice: str | None = None
    rate: int | None = None
    executable: str = "say"

    def speak(self, text: str) -> None:
        """Speak one text argument without invoking a shell."""
        if not text.strip():
            raise SpeechError("Cannot speak an empty narration.")
        if self.rate is not None and self.rate <= 0:
            raise SpeechError("Speech rate must be greater than zero.")

        command = [self.executable]
        if self.voice is not None:
            command.extend(["-v", self.voice])
        if self.rate is not None:
            command.extend(["-r", str(self.rate)])
        command.append(text)

        try:
            subprocess.run(command, check=True)
        except FileNotFoundError as error:
            raise SpeechError(
                "macOS text-to-speech is unavailable because the 'say' "
                "executable was not found."
            ) from error
        except subprocess.CalledProcessError as error:
            raise SpeechError(
                f"The macOS 'say' command failed with status {error.returncode}."
            ) from error


@dataclass
class CancellableMacSaySpeaker:
    """Speak one chunk at a time while allowing another thread to stop it."""

    voice: str | None = None
    rate: int | None = None
    executable: str = "say"
    poll_interval_seconds: float = 0.05
    _state_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _speak_lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )
    _process: subprocess.Popen | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _stop_requested: bool = field(default=False, init=False, repr=False)

    def _command(self, text: str) -> list[str]:
        if not text.strip():
            raise SpeechError("Cannot speak an empty narration.")
        if self.rate is not None and self.rate <= 0:
            raise SpeechError("Speech rate must be greater than zero.")
        if self.poll_interval_seconds <= 0:
            raise SpeechError("Speech poll interval must be greater than zero.")

        command = [self.executable]
        if self.voice is not None:
            command.extend(["-v", self.voice])
        if self.rate is not None:
            command.extend(["-r", str(self.rate)])
        command.append(text)
        return command

    def stop(self) -> bool:
        """Request cancellation and terminate the current process if present."""
        with self._state_lock:
            self._stop_requested = True
            process = self._process
        if process is None or process.poll() is not None:
            return False
        try:
            process.terminate()
        except ProcessLookupError:
            return False
        return True

    @staticmethod
    def _reap_cancelled_process(process: subprocess.Popen) -> None:
        if process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            process.wait()

    def speak(
        self,
        text: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> bool:
        """Return ``False`` when this chunk is deliberately interrupted."""
        command = self._command(text)
        if cancel_event is not None and cancel_event.is_set():
            return False

        with self._speak_lock:
            if cancel_event is not None and cancel_event.is_set():
                return False
            with self._state_lock:
                self._stop_requested = False

            try:
                process = subprocess.Popen(command)
            except FileNotFoundError as error:
                raise SpeechError(
                    "macOS text-to-speech is unavailable because the 'say' "
                    "executable was not found."
                ) from error

            with self._state_lock:
                self._process = process
                should_stop = self._stop_requested

            try:
                while True:
                    cancelled = (
                        cancel_event is not None and cancel_event.is_set()
                    )
                    with self._state_lock:
                        should_stop = should_stop or self._stop_requested
                    if cancelled or should_stop:
                        self._reap_cancelled_process(process)
                        return False
                    try:
                        return_code = process.wait(
                            timeout=self.poll_interval_seconds
                        )
                    except subprocess.TimeoutExpired:
                        continue

                    with self._state_lock:
                        should_stop = self._stop_requested
                    if should_stop or (
                        cancel_event is not None and cancel_event.is_set()
                    ):
                        return False
                    if return_code != 0:
                        raise SpeechError(
                            "The macOS 'say' command failed with status "
                            f"{return_code}."
                        )
                    return True
            except BaseException:
                self._reap_cancelled_process(process)
                raise
            finally:
                with self._state_lock:
                    if self._process is process:
                        self._process = None

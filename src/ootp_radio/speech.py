"""macOS text-to-speech support."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


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


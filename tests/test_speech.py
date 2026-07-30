"""Tests for safe macOS text-to-speech invocation."""

import subprocess
import threading
from unittest.mock import patch

import pytest

from ootp_radio.speech import (
    CancellableMacSaySpeaker,
    MacSaySpeaker,
    SpeechError,
)


def test_uses_the_configured_macos_voice_by_default() -> None:
    narration = "A safe recap; no shell interpretation $(ignored)."

    with patch("ootp_radio.speech.subprocess.run") as run:
        MacSaySpeaker().speak(narration)

    run.assert_called_once_with(["say", narration], check=True)


def test_passes_voice_rate_and_text_as_separate_arguments() -> None:
    narration = "The Orioles won."

    with patch("ootp_radio.speech.subprocess.run") as run:
        MacSaySpeaker(voice="Samantha", rate=185).speak(narration)

    run.assert_called_once_with(
        ["say", "-v", "Samantha", "-r", "185", narration],
        check=True,
    )


def test_missing_say_executable_has_a_useful_error() -> None:
    with patch(
        "ootp_radio.speech.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        with pytest.raises(SpeechError, match="'say' executable was not found"):
            MacSaySpeaker().speak("The Orioles won.")


def test_failed_say_command_has_a_useful_error() -> None:
    failure = subprocess.CalledProcessError(returncode=1, cmd=["say"])

    with patch(
        "ootp_radio.speech.subprocess.run",
        side_effect=failure,
    ):
        with pytest.raises(SpeechError, match="failed with status 1"):
            MacSaySpeaker().speak("The Orioles won.")


def test_cancellable_speaker_uses_safe_arguments_and_completes() -> None:
    with patch("ootp_radio.speech.subprocess.Popen") as popen:
        popen.return_value.wait.return_value = 0
        completed = CancellableMacSaySpeaker(
            voice="Samantha", rate=185
        ).speak("The Orioles won.")

    assert completed is True
    popen.assert_called_once_with(
        ["say", "-v", "Samantha", "-r", "185", "The Orioles won."]
    )


def test_cancellation_before_launch_does_not_start_say() -> None:
    cancel_event = threading.Event()
    cancel_event.set()

    with patch("ootp_radio.speech.subprocess.Popen") as popen:
        completed = CancellableMacSaySpeaker().speak(
            "The Orioles won.",
            cancel_event=cancel_event,
        )

    assert completed is False
    popen.assert_not_called()


def test_stop_terminates_active_say_without_reporting_failure() -> None:
    speaker = CancellableMacSaySpeaker()

    class FakeProcess:
        return_code: int | None = None
        wait_count = 0

        def poll(self):
            return self.return_code

        def terminate(self):
            self.return_code = -15

        def kill(self):
            self.return_code = -9

        def wait(self, timeout=None):
            self.wait_count += 1
            if self.wait_count == 1:
                speaker.stop()
                raise subprocess.TimeoutExpired(cmd=["say"], timeout=timeout)
            return self.return_code

    process = FakeProcess()
    with patch("ootp_radio.speech.subprocess.Popen", return_value=process):
        completed = speaker.speak("A long highlight call.")

    assert completed is False
    assert process.return_code == -15
    assert speaker.stop() is False


def test_cancellable_speaker_reports_unexpected_nonzero_exit() -> None:
    with patch("ootp_radio.speech.subprocess.Popen") as popen:
        popen.return_value.wait.return_value = 2
        with pytest.raises(SpeechError, match="failed with status 2"):
            CancellableMacSaySpeaker().speak("The Orioles won.")


def test_keyboard_interrupt_terminates_and_reaps_active_say() -> None:
    class InterruptedProcess:
        return_code: int | None = None
        terminated = False
        wait_count = 0

        def poll(self):
            return self.return_code

        def terminate(self):
            self.terminated = True
            self.return_code = -15

        def kill(self):
            self.return_code = -9

        def wait(self, timeout=None):
            self.wait_count += 1
            if self.wait_count == 1:
                raise KeyboardInterrupt
            return self.return_code

    process = InterruptedProcess()
    with patch("ootp_radio.speech.subprocess.Popen", return_value=process):
        with pytest.raises(KeyboardInterrupt):
            CancellableMacSaySpeaker().speak("A long highlight call.")

    assert process.terminated is True
    assert process.wait_count == 2

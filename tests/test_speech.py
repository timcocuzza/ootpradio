"""Tests for safe macOS text-to-speech invocation."""

import subprocess
from unittest.mock import patch

import pytest

from ootp_radio.speech import MacSaySpeaker, SpeechError


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


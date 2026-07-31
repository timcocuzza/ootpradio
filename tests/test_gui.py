"""Headless tests for desktop helpers that do not require a Tk window."""

import subprocess
from unittest.mock import patch

from ootp_radio.gui import SYSTEM_DEFAULT_VOICE, discover_macos_voices


def test_voice_discovery_keeps_system_default_and_multiword_names() -> None:
    output = (
        f"{'Alex':<20} en_US    # Hello\n"
        f"{'Bad News':<20} en_US    # Hello\n"
        f"{'Alex':<20} en_GB    # duplicate name\n"
    )
    completed = subprocess.CompletedProcess(
        args=["say", "-v", "?"],
        returncode=0,
        stdout=output,
        stderr="",
    )

    with patch("ootp_radio.gui.subprocess.run", return_value=completed):
        voices = discover_macos_voices()

    assert voices == (SYSTEM_DEFAULT_VOICE, "Alex", "Bad News")


def test_voice_discovery_failure_still_allows_system_default() -> None:
    with patch(
        "ootp_radio.gui.subprocess.run",
        side_effect=subprocess.TimeoutExpired("say", 3),
    ):
        assert discover_macos_voices() == (SYSTEM_DEFAULT_VOICE,)

"""Race-oriented tests for desktop Start, Stop Playback, and Stop Listening."""

import threading
from pathlib import Path

import pytest

from ootp_radio.app_settings import AppSettings
from ootp_radio.listening_session import (
    ListeningSession,
    SessionError,
    SessionStatus,
)
from ootp_radio.models import BroadcastSegment
from ootp_radio.paths import SaveDirectoryError


def _valid_save(tmp_path: Path) -> Path:
    save_dir = tmp_path / "League With Spaces.lg"
    (save_dir / "replays").mkdir(parents=True)
    (save_dir / "news" / "html" / "box_scores").mkdir(parents=True)
    return save_dir


class FakeController:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.fail = fail
        self.stop_playback_calls = 0
        self.stop_listening_calls = 0

    def run(self) -> None:
        self.started.set()
        if self.fail is not None:
            raise self.fail
        self.release.wait(timeout=5)

    def stop_playback(self) -> bool:
        self.stop_playback_calls += 1
        return True

    def stop_listening(self) -> None:
        self.stop_listening_calls += 1
        self.release.set()


def test_start_requires_selected_valid_save_before_building_controller(
    tmp_path: Path,
) -> None:
    builds = []
    session = ListeningSession(controller_factory=lambda **kwargs: builds.append(kwargs))

    with pytest.raises(SessionError, match="Choose an OOTP"):
        session.start(AppSettings())
    assert session.status is SessionStatus.STOPPED
    assert builds == []

    with pytest.raises(SaveDirectoryError, match="not ready"):
        session.start(AppSettings(save_dir=tmp_path / "Missing.lg"))
    assert session.status is SessionStatus.STOPPED
    assert builds == []


def test_start_forwards_every_gui_setting_and_runs_in_background(
    tmp_path: Path,
) -> None:
    controller = FakeController()
    received = {}

    def factory(**kwargs):
        received.update(kwargs)
        return controller

    settings = AppSettings(
        save_dir=_valid_save(tmp_path),
        voice="Samantha",
        rate=185,
        segments=(BroadcastSegment.SCORES, BroadcastSegment.NEWS),
        off_day_broadcasts=False,
        play_current=True,
        poll_interval_seconds=1.25,
    )
    session = ListeningSession(controller_factory=factory)

    session.start(settings)
    assert controller.started.wait(timeout=1)

    assert session.status is SessionStatus.LISTENING
    assert received == {
        "save_dir": settings.save_dir,
        "team_name": "Baltimore Orioles",
        "segments": settings.segments,
        "voice": "Samantha",
        "rate": 185,
        "poll_interval_seconds": 1.25,
        "play_current": True,
        "include_off_days": False,
    }
    session.stop_listening()
    assert session.wait(timeout=1)


def test_duplicate_start_is_rejected_without_replacing_active_controller(
    tmp_path: Path,
) -> None:
    controller = FakeController()
    session = ListeningSession(controller_factory=lambda **_: controller)
    settings = AppSettings(save_dir=_valid_save(tmp_path))
    session.start(settings)
    assert controller.started.wait(timeout=1)

    with pytest.raises(SessionError, match="already"):
        session.start(settings)

    session.stop_listening()
    assert session.wait(timeout=1)


def test_stop_playback_keeps_listening_then_full_stop_shuts_down(
    tmp_path: Path,
) -> None:
    controller = FakeController()
    statuses = []
    session = ListeningSession(
        controller_factory=lambda **_: controller,
        status_callback=lambda status, error: statuses.append((status, error)),
    )
    session.start(AppSettings(save_dir=_valid_save(tmp_path)))
    assert controller.started.wait(timeout=1)

    assert session.stop_playback() is True
    assert controller.stop_playback_calls == 1
    assert session.status is SessionStatus.LISTENING

    assert session.stop_listening() is True
    assert session.stop_listening() is False
    assert session.wait(timeout=1)
    assert controller.stop_listening_calls == 1
    assert session.status is SessionStatus.STOPPED
    assert [status for status, _ in statuses] == [
        SessionStatus.STARTING,
        SessionStatus.LISTENING,
        SessionStatus.STOPPING,
        SessionStatus.STOPPED,
    ]


def test_controller_failure_returns_to_stopped_and_reports_error(
    tmp_path: Path,
) -> None:
    failure = RuntimeError("speaker backend failed")
    controller = FakeController(fail=failure)
    stopped = threading.Event()
    updates = []

    def on_status(status, error):
        updates.append((status, error))
        if status is SessionStatus.STOPPED:
            stopped.set()

    session = ListeningSession(
        controller_factory=lambda **_: controller,
        status_callback=on_status,
    )
    session.start(AppSettings(save_dir=_valid_save(tmp_path)))

    assert stopped.wait(timeout=1)
    assert session.status is SessionStatus.STOPPED
    assert session.last_error is failure
    assert updates[-1] == (SessionStatus.STOPPED, failure)


def test_stop_playback_while_stopped_is_a_noop() -> None:
    session = ListeningSession(controller_factory=lambda **_: FakeController())

    assert session.stop_playback() is False
    assert session.stop_listening() is False

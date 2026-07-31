"""Race-oriented tests for latest-wins monitoring and cancellation."""

from pathlib import Path
from unittest.mock import patch

from ootp_radio.broadcast_controller import (
    LatestWinsBroadcastController,
    build_latest_wins_controller,
)
from ootp_radio.game_detector import GameNotReadyError, NoReplayFilesError
from ootp_radio.models import (
    BroadcastIssue,
    BroadcastSection,
    BroadcastSegment,
    GameDayEvent,
    GameFiles,
    GameResult,
    LeagueSlate,
    OffDayEvent,
)
from ootp_radio.radio_event import RadioEventNotReadyError


def _game(game_id: int) -> GameFiles:
    return GameFiles(
        game_id=game_id,
        replay_path=Path(f"replay_{game_id}.rpl"),
        box_score_path=Path(f"game_box_{game_id}.html"),
        game_log_path=None,
        highlight_path=Path(f"highlight_{game_id}.rpl"),
    )


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.stop_calls = 0
        self.on_speak = None

    def speak(self, text, *, cancel_event=None):
        self.spoken.append(text)
        if self.on_speak is not None:
            callback, self.on_speak = self.on_speak, None
            callback()
        return cancel_event is None or not cancel_event.is_set()

    def stop(self):
        self.stop_calls += 1
        return True


def _parts(game_files: GameFiles):
    yield BroadcastSection(
        BroadcastSegment.HIGHLIGHTS,
        (f"game {game_files.game_id} first", f"game {game_files.game_id} second"),
    )


def _controller(
    *,
    speaker: FakeSpeaker,
    detector,
    stabilizer=lambda _: None,
    play_current: bool = False,
    part_factory=_parts,
) -> LatestWinsBroadcastController:
    return LatestWinsBroadcastController(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        segments=(BroadcastSegment.HIGHLIGHTS,),
        speaker=speaker,
        play_current=play_current,
        detector=detector,
        stabilizer=stabilizer,
        part_factory=part_factory,
    )


def test_start_baselines_current_game_without_playing_it() -> None:
    speaker = FakeSpeaker()
    controller = _controller(speaker=speaker, detector=lambda _: _game(1))

    controller.initialize()

    assert controller.recognized_game_id == 1
    assert controller.pending_game_id is None
    assert controller.play_pending_once() is None
    assert speaker.spoken == []


def test_play_current_schedules_and_speaks_each_chunk() -> None:
    speaker = FakeSpeaker()
    controller = _controller(
        speaker=speaker,
        detector=lambda _: _game(1),
        play_current=True,
    )

    controller.initialize()

    assert controller.play_pending_once() is True
    assert speaker.spoken == ["game 1 first", "game 1 second"]
    assert controller.active_game_id is None


def test_new_game_interrupts_old_audio_and_only_newest_continues() -> None:
    speaker = FakeSpeaker()
    controller = _controller(
        speaker=speaker,
        detector=lambda _: _game(1),
        play_current=True,
    )
    controller.initialize()
    speaker.on_speak = lambda: controller.recognize_game(_game(2))

    assert controller.play_pending_once() is False
    assert controller.pending_game_id == 2
    assert speaker.stop_calls == 1
    assert speaker.spoken == ["game 1 first"]

    assert controller.play_pending_once() is True
    assert speaker.spoken == [
        "game 1 first",
        "game 2 first",
        "game 2 second",
    ]


def test_rapid_replacements_keep_only_latest_pending_game() -> None:
    speaker = FakeSpeaker()
    controller = _controller(
        speaker=speaker,
        detector=lambda _: _game(1),
    )
    controller.initialize()

    controller.recognize_game(_game(2))
    controller.recognize_game(_game(3))

    assert controller.pending_game_id == 3
    assert controller.play_pending_once() is True
    assert speaker.spoken == ["game 3 first", "game 3 second"]


def test_unstable_new_game_does_not_interrupt_current_audio() -> None:
    speaker = FakeSpeaker()
    detector_games = iter((_game(1), _game(2)))

    def detector(_):
        return next(detector_games)

    def stabilizer(game_files):
        if game_files.game_id == 2:
            raise GameNotReadyError("still being written")

    controller = _controller(
        speaker=speaker,
        detector=detector,
        stabilizer=stabilizer,
        play_current=True,
    )
    controller.initialize()
    speaker.on_speak = controller.poll_once

    assert controller.play_pending_once() is True
    assert speaker.stop_calls == 0
    assert speaker.spoken == ["game 1 first", "game 1 second"]
    assert controller.pending_game_id is None


def test_manual_stop_discards_audio_but_monitoring_can_continue() -> None:
    speaker = FakeSpeaker()
    controller = _controller(
        speaker=speaker,
        detector=lambda _: _game(1),
        play_current=True,
    )
    controller.initialize()
    speaker.on_speak = controller.stop_playback

    assert controller.play_pending_once() is False
    assert controller.pending_game_id is None
    assert speaker.spoken == ["game 1 first"]

    assert controller.recognize_game(_game(2)) is True
    assert controller.play_pending_once() is True
    assert speaker.spoken[-2:] == ["game 2 first", "game 2 second"]


def test_segment_issue_is_logged_not_spoken() -> None:
    speaker = FakeSpeaker()

    def parts(_):
        yield BroadcastIssue(BroadcastSegment.NEWS, "no headlines")
        yield BroadcastSection(BroadcastSegment.TEAM_RECAP, ("ready recap",))

    controller = _controller(
        speaker=speaker,
        detector=lambda _: _game(1),
        play_current=True,
        part_factory=parts,
    )
    controller.initialize()

    assert controller.play_pending_once() is True
    assert speaker.spoken == ["ready recap"]


def test_empty_save_then_first_stable_game_is_scheduled() -> None:
    speaker = FakeSpeaker()
    calls = 0

    def detector(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise NoReplayFilesError("none yet")
        return _game(1)

    controller = _controller(speaker=speaker, detector=detector)
    controller.initialize()

    assert controller.recognized_game_id is None
    assert controller.poll_once() is True
    assert controller.pending_game_id == 1


def test_repeated_poll_of_same_game_never_replays_it() -> None:
    speaker = FakeSpeaker()
    controller = _controller(
        speaker=speaker,
        detector=lambda _: _game(1),
        play_current=True,
    )
    controller.initialize()
    assert controller.play_pending_once() is True

    assert controller.poll_once() is False
    assert controller.play_pending_once() is None
    assert speaker.spoken == ["game 1 first", "game 1 second"]


def _slate(date: str, game_id: int = 50) -> LeagueSlate:
    return LeagueSlate(
        date,
        (
            GameResult(
                game_id,
                date,
                "Seattle Mariners",
                5,
                "Texas Rangers",
                3,
                24,
                28,
            ),
        ),
        game_id * 1_000_000_000,
    )


def _event_parts(target):
    if isinstance(target, OffDayEvent):
        yield BroadcastSection(
            BroadcastSegment.SCORES,
            (f"off day {target.slate.date}",),
        )
    else:
        yield from _parts(target)


def _event_controller(*, speaker, event_detector, play_current=False):
    return LatestWinsBroadcastController(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        segments=(BroadcastSegment.SCORES,),
        speaker=speaker,
        play_current=play_current,
        event_detector=event_detector,
        part_factory=_event_parts,
    )


def test_start_can_baseline_off_day_without_playing_it() -> None:
    speaker = FakeSpeaker()
    event = OffDayEvent(_slate("08/04/2032"))
    controller = _event_controller(
        speaker=speaker,
        event_detector=lambda: event,
    )

    controller.initialize()

    assert controller.recognized_event_key == "off-day:08/04/2032"
    assert controller.pending_event_key is None
    assert controller.recognized_game_id is None
    assert speaker.spoken == []


def test_new_off_day_interrupts_game_audio_without_queuing() -> None:
    speaker = FakeSpeaker()
    game_event = GameDayEvent(_game(1), _slate("08/03/2032", 1))
    off_day = OffDayEvent(_slate("08/04/2032", 2))
    controller = _event_controller(
        speaker=speaker,
        event_detector=lambda: game_event,
        play_current=True,
    )
    controller.initialize()
    speaker.on_speak = lambda: controller.recognize_event(off_day)

    assert controller.play_pending_once() is False
    assert controller.pending_event_key == "off-day:08/04/2032"
    assert speaker.stop_calls == 1

    assert controller.play_pending_once() is True
    assert speaker.spoken == ["game 1 first", "off day 08/04/2032"]


def test_same_off_day_date_never_replays_when_slate_object_changes() -> None:
    speaker = FakeSpeaker()
    first = OffDayEvent(_slate("08/04/2032", 50))
    updated = OffDayEvent(_slate("08/04/2032", 51))
    events = iter((first, updated))
    controller = _event_controller(
        speaker=speaker,
        event_detector=lambda: next(events),
        play_current=True,
    )
    controller.initialize()
    assert controller.play_pending_once() is True

    assert controller.poll_once() is False
    assert controller.play_pending_once() is None
    assert speaker.spoken == ["off day 08/04/2032"]


def test_not_ready_team_event_does_not_interrupt_current_audio() -> None:
    speaker = FakeSpeaker()
    off_day = OffDayEvent(_slate("08/04/2032", 50))
    calls = 0

    def detect_event():
        nonlocal calls
        calls += 1
        if calls == 1:
            return off_day
        raise RadioEventNotReadyError("team replay is still settling")

    controller = _event_controller(
        speaker=speaker,
        event_detector=detect_event,
        play_current=True,
    )
    controller.initialize()
    speaker.on_speak = controller.poll_once

    assert controller.play_pending_once() is True
    assert speaker.stop_calls == 0
    assert speaker.spoken == ["off day 08/04/2032"]


def test_disabled_off_day_audio_is_recognized_but_safely_silent() -> None:
    speaker = FakeSpeaker()
    off_day = OffDayEvent(_slate("08/04/2032", 50))
    controller = LatestWinsBroadcastController(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        segments=(BroadcastSegment.SCORES,),
        speaker=speaker,
        play_current=True,
        event_detector=lambda: off_day,
        include_off_days=False,
    )

    controller.initialize()

    assert controller.recognized_event_key == "off-day:08/04/2032"
    assert controller.play_pending_once() is True
    assert speaker.spoken == []


def test_production_builder_passes_persisted_team_id_to_detector() -> None:
    with patch(
        "ootp_radio.broadcast_controller.LatestRadioEventDetector"
    ) as detector_class:
        controller = build_latest_wins_controller(
            save_dir=Path("League.lg"),
            team_name="Baltimore Orioles",
            team_id=3,
            segments=(BroadcastSegment.HIGHLIGHTS,),
        )

    detector_class.assert_called_once_with(
        save_dir=Path("League.lg"),
        team_name="Baltimore Orioles",
        team_id=3,
    )
    assert controller.event_detector is detector_class.return_value.detect

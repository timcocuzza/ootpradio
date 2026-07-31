"""Tests for persisted desktop settings and drag-order rules."""

import json
from pathlib import Path

import pytest

from ootp_radio.app_settings import (
    AppSettings,
    SettingsError,
    load_settings,
    move_segment,
    save_settings,
    set_segment_enabled,
)
from ootp_radio.models import BroadcastSegment


def test_missing_settings_file_loads_safe_defaults(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.json")

    assert settings.save_dir is None
    assert settings.team_name == "Baltimore Orioles"
    assert settings.voice is None
    assert settings.rate is None
    assert settings.off_day_broadcasts is True
    assert settings.play_current is False
    assert settings.segments[-1] is BroadcastSegment.NEWS


def test_settings_round_trip_atomically_with_news_last(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "settings.json"
    settings = AppSettings(
        save_dir=Path("/tmp/League With Spaces.lg"),
        team_name="Baltimore Orioles",
        voice="Alex",
        rate=190,
        segments=(
            BroadcastSegment.NEWS,
            BroadcastSegment.SCORES,
            BroadcastSegment.HIGHLIGHTS,
        ),
        off_day_broadcasts=False,
        play_current=True,
        poll_interval_seconds=1.5,
    )

    saved_path = save_settings(settings, path)
    loaded = load_settings(path)

    assert saved_path == path
    assert loaded == settings
    assert loaded.segments == (
        BroadcastSegment.SCORES,
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.NEWS,
    )
    assert not (path.parent / ".settings.json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_corrupted_settings_are_reported_instead_of_silently_overwritten(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SettingsError, match="not valid JSON"):
        load_settings(path)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"segments": []}, "at least one"),
        ({"segments": ["scores", "scores"]}, "only once"),
        ({"segments": ["future-option"]}, "unknown"),
        ({"rate": 0}, "positive whole number"),
        ({"off_day_broadcasts": "yes"}, "true or false"),
        ({"version": 99}, "Unsupported settings version"),
    ],
)
def test_invalid_persisted_values_have_clear_errors(override, message) -> None:
    document = {"version": 1, **override}

    with pytest.raises(SettingsError, match=message):
        AppSettings.from_json(document)


def test_dragging_news_or_dragging_past_it_keeps_news_last() -> None:
    order = (
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.TEAM_RECAP,
        BroadcastSegment.SCORES,
        BroadcastSegment.NEWS,
    )

    assert move_segment(order, source_index=3, target_index=0) == order
    assert move_segment(order, source_index=0, target_index=3) == (
        BroadcastSegment.TEAM_RECAP,
        BroadcastSegment.SCORES,
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.NEWS,
    )


def test_drag_indices_outside_list_are_rejected() -> None:
    with pytest.raises(SettingsError, match="source"):
        move_segment(
            (BroadcastSegment.SCORES,),
            source_index=-1,
            target_index=0,
        )


def test_segment_toggles_preserve_order_and_one_required_option() -> None:
    order = (BroadcastSegment.HIGHLIGHTS, BroadcastSegment.NEWS)

    order = set_segment_enabled(
        order,
        BroadcastSegment.SCORES,
        enabled=True,
    )
    assert order == (
        BroadcastSegment.HIGHLIGHTS,
        BroadcastSegment.SCORES,
        BroadcastSegment.NEWS,
    )
    order = set_segment_enabled(
        order,
        BroadcastSegment.HIGHLIGHTS,
        enabled=False,
    )
    order = set_segment_enabled(
        order,
        BroadcastSegment.NEWS,
        enabled=False,
    )
    with pytest.raises(SettingsError, match="At least one"):
        set_segment_enabled(
            order,
            BroadcastSegment.SCORES,
            enabled=False,
        )

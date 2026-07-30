"""Tests for read-only saved-league path validation."""

from pathlib import Path

from ootp_radio.paths import CheckStatus, validate_save_dir


def _create_save_dir(tmp_path: Path, *, include_optional: bool = True) -> Path:
    save_dir = tmp_path / "League With Spaces.lg"
    (save_dir / "replays").mkdir(parents=True)
    (save_dir / "news" / "html" / "box_scores").mkdir(parents=True)

    if include_optional:
        (save_dir / "news" / "txt" / "leagues").mkdir(parents=True)
        (save_dir / "messages").mkdir()
        (save_dir / "news" / "html" / "leagues").mkdir()

    return save_dir


def _statuses_by_name(save_dir: Path) -> dict[str, CheckStatus]:
    report = validate_save_dir(save_dir)
    return {check.name: check.status for check in report.checks}


def test_valid_save_passes_all_directory_checks(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)

    report = validate_save_dir(save_dir)

    assert report.is_healthy
    assert all(check.status is CheckStatus.PASS for check in report.checks)


def test_missing_required_directory_fails_validation(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path)
    (save_dir / "replays").rmdir()

    report = validate_save_dir(save_dir)

    assert not report.is_healthy
    assert _statuses_by_name(save_dir)["replays"] is CheckStatus.FAIL


def test_missing_save_directory_fails_validation(tmp_path: Path) -> None:
    save_dir = tmp_path / "Missing League.lg"

    report = validate_save_dir(save_dir)

    assert not report.is_healthy
    assert _statuses_by_name(save_dir)["save_dir"] is CheckStatus.FAIL


def test_missing_optional_directories_warn_without_failing(tmp_path: Path) -> None:
    save_dir = _create_save_dir(tmp_path, include_optional=False)

    report = validate_save_dir(save_dir)
    statuses = _statuses_by_name(save_dir)

    assert report.is_healthy
    assert statuses["game_logs"] is CheckStatus.WARN
    assert statuses["messages"] is CheckStatus.WARN
    assert statuses["league_reports"] is CheckStatus.WARN


def test_non_lg_directory_fails_validation(tmp_path: Path) -> None:
    save_dir = tmp_path / "Not A League"
    (save_dir / "replays").mkdir(parents=True)
    (save_dir / "news" / "html" / "box_scores").mkdir(parents=True)

    report = validate_save_dir(save_dir)

    assert not report.is_healthy
    assert _statuses_by_name(save_dir)["save_extension"] is CheckStatus.FAIL


def test_file_cannot_be_used_as_the_save_directory(tmp_path: Path) -> None:
    save_file = tmp_path / "baseball.lg"
    save_file.write_text("not a directory", encoding="utf-8")

    report = validate_save_dir(save_file)

    assert not report.is_healthy
    assert _statuses_by_name(save_file)["save_dir"] is CheckStatus.FAIL

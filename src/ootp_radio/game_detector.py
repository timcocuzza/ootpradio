"""Detect the newest played game from OOTP replay files."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path
from stat import S_ISREG

from ootp_radio.models import GameFiles

_REPLAY_FILENAME = re.compile(r"replay_(\d+)\.rpl")


class GameDetectionError(RuntimeError):
    """Base class for expected latest-game detection failures."""


class NoReplayFilesError(GameDetectionError):
    """Raised when no played-game replay is available."""


class GameNotReadyError(GameDetectionError):
    """Raised when a game's required files are missing or changing."""


def _replay_candidates(replays_dir: Path) -> list[tuple[int, int, Path]]:
    try:
        entries = list(replays_dir.iterdir())
    except FileNotFoundError as error:
        raise GameDetectionError(
            f"The replays directory does not exist: '{replays_dir}'. "
            "Run the doctor command and check the selected save directory."
        ) from error
    except OSError as error:
        raise GameDetectionError(
            f"Could not inspect the replays directory '{replays_dir}': {error}."
        ) from error

    candidates: list[tuple[int, int, Path]] = []
    for entry in entries:
        filename_match = _REPLAY_FILENAME.fullmatch(entry.name)
        if filename_match is None:
            continue

        try:
            entry_stat = entry.stat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise GameDetectionError(
                f"Could not inspect replay file '{entry}': {error}."
            ) from error

        if S_ISREG(entry_stat.st_mode):
            candidates.append(
                (entry_stat.st_mtime_ns, int(filename_match.group(1)), entry)
            )

    return candidates


def _require_regular_file(path: Path, *, game_id: int) -> None:
    try:
        path_stat = path.stat()
    except FileNotFoundError as error:
        raise GameNotReadyError(
            f"The latest replay is game {game_id}, but {path.name} is not "
            "ready yet. Try again after OOTP finishes writing the game."
        ) from error
    except OSError as error:
        raise GameDetectionError(f"Could not inspect '{path}': {error}.") from error

    if not S_ISREG(path_stat.st_mode):
        raise GameNotReadyError(
            f"The latest replay is game {game_id}, but {path.name} is not a "
            "readable file yet."
        )


def _optional_regular_file(path: Path) -> Path | None:
    try:
        path_stat = path.stat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise GameDetectionError(f"Could not inspect '{path}': {error}.") from error
    return path if S_ISREG(path_stat.st_mode) else None


def detect_latest_game(save_dir: Path | str) -> GameFiles:
    """Resolve matching files for the newest numeric played-game replay."""
    save_path = Path(save_dir)
    candidates = _replay_candidates(save_path / "replays")
    if not candidates:
        raise NoReplayFilesError(
            "No replay_<GAME_ID>.rpl files were found. Complete a played game "
            "in OOTP, then try again."
        )

    _, game_id, replay_path = max(candidates, key=lambda candidate: candidate[:2])
    box_score_path = (
        save_path / "news" / "html" / "box_scores" / f"game_box_{game_id}.html"
    )
    _require_regular_file(box_score_path, game_id=game_id)

    game_log_path = (
        save_path / "news" / "txt" / "leagues" / f"log_{game_id}.txt"
    )
    highlight_path = save_path / "replays" / f"highlight_{game_id}.rpl"

    return GameFiles(
        game_id=game_id,
        replay_path=replay_path,
        box_score_path=box_score_path,
        game_log_path=_optional_regular_file(game_log_path),
        highlight_path=_optional_regular_file(highlight_path),
    )


def _file_snapshot(path: Path) -> tuple[int, int]:
    try:
        path_stat = path.stat()
    except FileNotFoundError as error:
        raise GameNotReadyError(
            f"{path.name} disappeared while its stability was being checked. "
            "Try again after OOTP finishes writing the game."
        ) from error
    except OSError as error:
        raise GameDetectionError(f"Could not inspect '{path}': {error}.") from error
    if not S_ISREG(path_stat.st_mode):
        raise GameNotReadyError(
            f"{path.name} is no longer a regular file. Try again after OOTP "
            "finishes writing the game."
        )
    return path_stat.st_size, path_stat.st_mtime_ns


def ensure_game_files_stable(
    game_files: GameFiles,
    *,
    poll_interval_seconds: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Require replay and box-score metadata to match across two polls."""
    if poll_interval_seconds < 0:
        raise ValueError("poll_interval_seconds cannot be negative")

    required_paths = (game_files.replay_path, game_files.box_score_path)
    first_snapshots = {path: _file_snapshot(path) for path in required_paths}
    sleep(poll_interval_seconds)

    for path in required_paths:
        if _file_snapshot(path) != first_snapshots[path]:
            raise GameNotReadyError(
                f"{path.name} is still being written by OOTP. Try again in a moment."
            )

"""Read-only validation of an OOTP saved-league directory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from stat import S_ISDIR


class CheckStatus(str, Enum):
    """Outcome of one doctor check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class SaveDirectoryError(RuntimeError):
    """Raised when a command cannot use the selected save directory."""


@dataclass(frozen=True)
class PathCheck:
    """Result of checking one expected path."""

    name: str
    path: Path
    status: CheckStatus
    message: str

    def render(self) -> str:
        """Render a concise, user-facing status line."""
        return f"{self.status.value}: {self.message} — {self.path}"


@dataclass(frozen=True)
class DoctorReport:
    """All path checks for one selected save directory."""

    checks: tuple[PathCheck, ...]

    @property
    def is_healthy(self) -> bool:
        """Return whether all required checks passed."""
        return all(check.status is not CheckStatus.FAIL for check in self.checks)


@dataclass(frozen=True)
class _DirectoryRequirement:
    name: str
    relative_path: Path
    required: bool


_DIRECTORY_REQUIREMENTS = (
    _DirectoryRequirement("replays", Path("replays"), True),
    _DirectoryRequirement(
        "box_scores", Path("news") / "html" / "box_scores", True
    ),
    _DirectoryRequirement(
        "game_logs", Path("news") / "txt" / "leagues", False
    ),
    _DirectoryRequirement("messages", Path("messages"), False),
    _DirectoryRequirement(
        "league_reports", Path("news") / "html" / "leagues", False
    ),
)


def _check_directory(
    *, name: str, path: Path, required: bool, display_name: str | None = None
) -> PathCheck:
    label = display_name or f"{name} directory"
    try:
        path_stat = path.stat()
    except FileNotFoundError:
        path_stat = None
    except OSError as error:
        return PathCheck(
            name=name,
            path=path,
            status=CheckStatus.FAIL if required else CheckStatus.WARN,
            message=f"{label} cannot be inspected: {error}",
        )

    if path_stat is not None:
        if S_ISDIR(path_stat.st_mode):
            return PathCheck(
                name=name,
                path=path,
                status=CheckStatus.PASS,
                message=f"{label} exists",
            )
        return PathCheck(
            name=name,
            path=path,
            status=CheckStatus.FAIL,
            message=f"{label} is not a directory",
        )

    status = CheckStatus.FAIL if required else CheckStatus.WARN
    requirement = "required" if required else "optional"
    return PathCheck(
        name=name,
        path=path,
        status=status,
        message=f"{label} is missing ({requirement})",
    )


def validate_save_dir(save_dir: Path | str) -> DoctorReport:
    """Inspect expected paths without reading or modifying save contents."""
    selected_path = Path(save_dir)
    checks = [
        _check_directory(
            name="save_dir",
            path=selected_path,
            required=True,
            display_name="save directory",
        )
    ]

    if selected_path.suffix.casefold() == ".lg":
        checks.append(
            PathCheck(
                name="save_extension",
                path=selected_path,
                status=CheckStatus.PASS,
                message="save directory has an .lg extension",
            )
        )
    else:
        checks.append(
            PathCheck(
                name="save_extension",
                path=selected_path,
                status=CheckStatus.FAIL,
                message="selected folder is not an .lg directory",
            )
        )

    for requirement in _DIRECTORY_REQUIREMENTS:
        checks.append(
            _check_directory(
                name=requirement.name,
                path=selected_path / requirement.relative_path,
                required=requirement.required,
            )
        )

    return DoctorReport(checks=tuple(checks))


def require_valid_save_dir(save_dir: Path | str) -> None:
    """Raise a concise error when required save-directory checks fail."""
    report = validate_save_dir(save_dir)
    failures = [
        check.message
        for check in report.checks
        if check.status is CheckStatus.FAIL
    ]
    if failures:
        detail = "; ".join(failures)
        raise SaveDirectoryError(
            f"The selected save directory is not ready: {detail}. "
            "Run the doctor command for a complete path report."
        )

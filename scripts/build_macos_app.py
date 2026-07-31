"""Build and verify the local arm64 OOTP Radio macOS application bundle."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = PROJECT_ROOT / "macos" / "OOTP Radio.spec"
APP_PATH = PROJECT_ROOT / "dist" / "OOTP Radio.app"
EXPAT_LIBRARY_DIR = Path("/opt/homebrew/opt/expat/lib")
PYINSTALLER_CONFIG_DIR = PROJECT_ROOT / "build" / "pyinstaller-config"


class AppBuildError(RuntimeError):
    """Raised when prerequisites, bundle generation, or verification fails."""


def packaging_environment(
    base: Mapping[str, str] | None = None,
    *,
    expat_library_dir: Path = EXPAT_LIBRARY_DIR,
) -> dict[str, str]:
    """Return a self-contained environment for build subprocesses."""
    environment = dict(os.environ if base is None else base)
    environment["PYINSTALLER_CONFIG_DIR"] = str(PYINSTALLER_CONFIG_DIR)
    if sys.platform != "darwin" or not expat_library_dir.is_dir():
        return environment
    existing = environment.get("DYLD_LIBRARY_PATH", "")
    search_paths = [str(expat_library_dir)]
    if existing:
        search_paths.append(existing)
    environment["DYLD_LIBRARY_PATH"] = os.pathsep.join(search_paths)
    return environment


def build_command() -> tuple[str, ...]:
    """Return the reproducible PyInstaller command rooted in this repository."""
    return (
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(PROJECT_ROOT / "dist"),
        "--workpath",
        str(PROJECT_ROOT / "build"),
        str(SPEC_PATH),
    )


def _plist_value(key: str) -> str:
    completed = subprocess.run(
        [
            "/usr/libexec/PlistBuddy",
            "-c",
            f"Print :{key}",
            str(APP_PATH / "Contents" / "Info.plist"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify_app_bundle() -> None:
    """Require the expected metadata, arm64 executable, and valid signature."""
    executable_path = APP_PATH / "Contents" / "MacOS" / "OOTP Radio"
    required_paths = (
        APP_PATH / "Contents" / "Info.plist",
        executable_path,
        APP_PATH / "Contents" / "Frameworks",
        APP_PATH / "Contents" / "Resources",
    )
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise AppBuildError(
            "The app bundle is incomplete; missing: " + ", ".join(missing)
        )
    if _plist_value("CFBundleIdentifier") != "com.timcocuzza.ootpradio":
        raise AppBuildError("The app bundle identifier is incorrect.")
    if _plist_value("CFBundleDisplayName") != "OOTP Radio":
        raise AppBuildError("The app display name is incorrect.")

    architecture = subprocess.run(
        ["file", str(executable_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if "arm64" not in architecture:
        raise AppBuildError(
            f"Expected an arm64 executable, but file reported: {architecture.strip()}"
        )
    subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(APP_PATH)],
        check=True,
    )


def main() -> int:
    if sys.platform != "darwin":
        raise AppBuildError("The macOS application must be built on macOS.")
    if importlib.util.find_spec("PyInstaller") is None:
        raise AppBuildError(
            "PyInstaller is not installed. Run: "
            "python3 -m pip install -e '.[package]'"
        )
    subprocess.run(
        build_command(),
        cwd=PROJECT_ROOT,
        env=packaging_environment(),
        check=True,
    )
    verify_app_bundle()
    print(f"Built and verified: {APP_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AppBuildError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

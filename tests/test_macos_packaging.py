"""Tests for the reproducible macOS application-bundle configuration."""

import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

from scripts.build_macos_app import (
    PROJECT_ROOT,
    PYINSTALLER_CONFIG_DIR,
    build_command,
    packaging_environment,
)


def test_packaging_extra_has_bounded_pyinstaller_version() -> None:
    project = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert project["project"]["optional-dependencies"]["package"] == [
        "pyinstaller>=6.21,<7"
    ]


def test_build_command_uses_current_interpreter_and_committed_spec() -> None:
    command = build_command()

    assert command[:3] == (sys.executable, "-m", "PyInstaller")
    assert "--clean" in command
    assert command[-1] == str(PROJECT_ROOT / "macos" / "OOTP Radio.spec")


def test_homebrew_expat_workaround_is_scoped_and_preserves_existing_path(
    tmp_path: Path,
) -> None:
    expat_dir = tmp_path / "expat" / "lib"
    expat_dir.mkdir(parents=True)

    with patch("scripts.build_macos_app.sys.platform", "darwin"):
        environment = packaging_environment(
            {"PATH": "/usr/bin", "DYLD_LIBRARY_PATH": "/existing/lib"},
            expat_library_dir=expat_dir,
        )

    assert environment["PATH"] == "/usr/bin"
    assert environment["PYINSTALLER_CONFIG_DIR"] == str(
        PYINSTALLER_CONFIG_DIR
    )
    assert environment["DYLD_LIBRARY_PATH"] == (
        f"{expat_dir}:/existing/lib"
    )


def test_non_macos_build_environment_is_unchanged(tmp_path: Path) -> None:
    expat_dir = tmp_path / "expat" / "lib"
    expat_dir.mkdir(parents=True)
    original = {"PATH": "/usr/bin"}

    with patch("scripts.build_macos_app.sys.platform", "linux"):
        environment = packaging_environment(
            original,
            expat_library_dir=expat_dir,
        )

    assert environment == {
        **original,
        "PYINSTALLER_CONFIG_DIR": str(PYINSTALLER_CONFIG_DIR),
    }


def test_spec_builds_windowed_arm64_app_with_expected_identity() -> None:
    spec = (PROJECT_ROOT / "macos" / "OOTP Radio.spec").read_text(
        encoding="utf-8"
    )
    entry = (PROJECT_ROOT / "macos" / "ootp_radio_app.py").read_text(
        encoding="utf-8"
    )

    assert 'console=False' in spec
    assert 'target_arch="arm64"' in spec
    assert 'name="OOTP Radio.app"' in spec
    assert 'bundle_identifier="com.timcocuzza.ootpradio"' in spec
    assert "from ootp_radio.gui import main" in entry

"""Tests for the local Streamlit launcher."""

from pathlib import Path
import runpy
import subprocess

import pytest

from researchmind import launcher


SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "run_app.py"


def test_launcher_suppresses_streamlit_email_prompt_and_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_command: list[str] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        recorded_command.extend(command)
        assert check is True

    monkeypatch.setattr(subprocess, "run", fake_run)

    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert "--server.headless=false" in recorded_command
    assert "--server.showEmailPrompt=false" in recorded_command
    assert "--browser.gatherUsageStats=false" in recorded_command


def test_packaged_launcher_targets_the_installed_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_command: list[str] = []

    def fake_run(command: list[str], *, check: bool) -> None:
        recorded_command.extend(command)
        assert check is True

    monkeypatch.setattr(subprocess, "run", fake_run)

    launcher.main(["--server.headless=true", "--server.port=8511"])

    app_path = Path(recorded_command[4])
    assert app_path == Path(launcher.__file__).resolve().parent / "app" / "app.py"
    assert app_path.is_file()
    assert recorded_command[-2:] == [
        "--server.headless=true",
        "--server.port=8511",
    ]


def test_launcher_stops_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupted_run(command: list[str], *, check: bool) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "run", interrupted_run)

    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

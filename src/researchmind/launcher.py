"""Launch the packaged ResearchMind Streamlit application."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys


def main(argv: Sequence[str] | None = None) -> None:
    """Run the package-owned Streamlit entry point with safe local defaults."""

    app_path = Path(__file__).resolve().parent / "app" / "app.py"
    extra_options = list(sys.argv[1:] if argv is None else argv)
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                "--server.headless=false",
                "--server.showEmailPrompt=false",
                "--browser.gatherUsageStats=false",
                *extra_options,
            ],
            check=True,
        )
    except KeyboardInterrupt:
        pass

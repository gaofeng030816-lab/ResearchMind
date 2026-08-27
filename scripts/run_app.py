"""Launch the ResearchMind Streamlit application with the active Python."""

from pathlib import Path
import subprocess
import sys


def main() -> None:
    app_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "researchmind"
        / "app"
        / "app.py"
    )
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
            ],
            check=True,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

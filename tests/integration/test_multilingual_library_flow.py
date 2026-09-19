"""V3-G6 managed mixed-language import integration coverage."""

from pathlib import Path

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.models import UploadedFileData


def test_mixed_language_directory_persists_and_reopens(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    uploads = [
        UploadedFileData(
            name="mixed/main.py",
            content=b"def main():\n    return 1\n",
        ),
        UploadedFileData(
            name="mixed/native/main.c",
            content=b"int main(void) { return 0; }\n",
        ),
        UploadedFileData(
            name="mixed/native/api.h",
            content=b"int run(void);\n",
        ),
        UploadedFileData(
            name="mixed/java/Main.java",
            content=b"class Main { int run() { return 1; } }\n",
        ),
        UploadedFileData(
            name="mixed/julia/main.jl",
            content=b"function run(x)\n    x + 1\nend\n",
        ),
        UploadedFileData(
            name="mixed/r/main.R",
            content=b"run <- function(x) { x + 1 }\n",
        ),
        UploadedFileData(
            name="mixed/r/credentials.R",
            content=b"TOKEN <- 'excluded'\n",
        ),
        UploadedFileData(
            name="mixed/vendor/ignored.c",
            content=b"int ignored;\n",
        ),
    ]

    imported = use_cases.import_code_directory_to_library(
        uploads,
        settings=settings,
    )
    reopened = use_cases.open_library_code_project(
        imported.entry.record.id,
        settings=settings,
    )
    summary = use_cases.get_code_project_summary(reopened)

    assert imported.entry.asset.media_type == (
        "application/vnd.researchmind.code-directory"
    )
    assert reopened.managed_by_researchmind is True
    assert [item.relative_path for item in reopened.files] == [
        "java/Main.java",
        "julia/main.jl",
        "main.py",
        "native/api.h",
        "native/main.c",
        "r/main.R",
    ]
    assert summary.languages == ("c", "java", "julia", "python", "r")
    assert not (reopened.root_path / "r" / "credentials.R").exists()
    assert not (reopened.root_path / "vendor").exists()

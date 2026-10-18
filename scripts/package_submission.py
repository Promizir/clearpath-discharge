"""Create separate source and presentation archives from an explicit allowlist."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission"
SOURCE_FILES = [
    "README.md", "pyproject.toml", "requirements.txt", "Dockerfile", ".dockerignore",
    ".gitignore", ".env.example", "render.yaml", "mock_ehr.json",
]


def build():
    source = [ROOT / name for name in SOURCE_FILES]
    source.extend(ROOT.glob("*.py"))
    for folder in ("static", "tests", "scripts", "docs"):
        source.extend(path for path in (ROOT / folder).rglob("*")
                      if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    # Keep the repository README illustration and submission text with source.
    source.extend(OUT / name for name in ("SUBMISSION.md", "DEMO_SCRIPT.md"))
    source.extend(OUT / name for name in ("VERIFICATION.md", "amd-execution-evidence.json") if (OUT / name).exists())
    source.extend((OUT / "screenshots").glob("*.png"))
    artifacts = [path for path in OUT.iterdir()
                 if path.is_file() and path.suffix in {".png", ".pdf", ".pptx", ".mp4", ".html", ".md", ".svg", ".json"}]
    for name, paths in (("ClearPath-source.zip", source), ("ClearPath-presentation.zip", artifacts)):
        with ZipFile(OUT / name, "w", ZIP_DEFLATED) as archive:
            for path in sorted(set(paths)):
                relative = path.relative_to(ROOT)
                assert not any(part in {".env", "runtime", ".venv", ".git", ".browser-cache"} for part in relative.parts)
                archive.write(path, relative.as_posix())
        with ZipFile(OUT / name) as archive:
            assert archive.testzip() is None
            print(f"{name}: {len(archive.namelist())} files, {(OUT/name).stat().st_size/1024/1024:.1f} MB; archive verified")


if __name__ == "__main__":
    build()

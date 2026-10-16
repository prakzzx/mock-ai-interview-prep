"""Static checks on the project: config files, branding, Docker, README."""

import json
import re
import tomllib
from pathlib import Path

import pytest

import app

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".json", ".txt", ".cfg", ".yml", ".yaml"}
TEXT_NAMES = {"Dockerfile", "Makefile", ".gitignore", ".dockerignore", ".env.example"}

# Built from pieces so that this file does not match its own search
OLD_TITLE = "AI Interview" + " System"
OLD_EMOJI = "\U0001f916"


def project_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES:
            yield path


def test_old_title_and_emoji_appear_nowhere():
    offenders = []
    for path in project_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if OLD_TITLE in text or OLD_EMOJI in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_no_todo_or_placeholder_markers_in_code():
    pattern = re.compile(r"\b(TODO|FIXME|XXX|placeholder)\b", re.IGNORECASE)
    offenders = []
    for path in ROOT.rglob("*.py"):
        if (
            SKIP_DIRS & set(path.relative_to(ROOT).parts)
            or path.name == Path(__file__).name
        ):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def test_no_bare_ellipsis_statements_in_code():
    """`...` is only allowed inside user-facing strings (e.g. spinner texts)."""
    offenders = []
    for path in ROOT.rglob("*.py"):
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip() in {"...", "pass  # ..."}:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def test_app_branding_constants():
    assert app.APP_NAME == "Interview Prep"
    assert app.APP_EMOJI == "🎤"
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'APP_NAME = "Interview Prep"' in source
    assert 'APP_EMOJI = "🎤"' in source


def test_streamlit_theme_config():
    config = tomllib.loads(
        (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    )
    theme = config["theme"]
    assert theme["base"] == "light"
    assert theme["font"] == "sans serif"
    assert theme["textColor"] == "#4A1530"
    for key in (
        "primaryColor",
        "backgroundColor",
        "secondaryBackgroundColor",
        "textColor",
    ):
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", theme[key]), key
    # the CSS palette and the Streamlit theme agree
    assert theme["backgroundColor"].upper() == app.PALETTE["background"].upper()
    assert theme["secondaryBackgroundColor"].upper() == app.PALETTE["surface"].upper()
    assert theme["primaryColor"].upper() == app.PALETTE["accent"].upper()
    assert theme["textColor"].upper() == app.PALETTE["text"].upper()


def test_vscode_files_are_valid_json():
    for name in ("launch.json", "settings.json", "extensions.json"):
        json.loads((ROOT / ".vscode" / name).read_text(encoding="utf-8"))


def test_launch_json_is_portable():
    launch = json.loads((ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8"))
    streamlit = next(
        c for c in launch["configurations"] if c.get("module") == "streamlit"
    )
    assert streamlit["args"] == ["run", "app.py"]
    assert streamlit["request"] == "launch"
    raw = (ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8")
    assert "pythonPath" not in raw and '"python":' not in raw
    assert not re.search(
        r"[A-Za-z]:\\\\|/usr/|/home/|/Users/", raw
    )  # no absolute paths


def test_settings_do_not_hard_code_an_interpreter():
    raw = (ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8")
    assert "defaultInterpreterPath" not in raw and "pythonPath" not in raw


def test_dockerfile_does_not_copy_the_env_file():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert not re.search(r"^\s*COPY\s+\.env", dockerfile, re.MULTILINE)
    assert ".env" in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "--env-file" in (ROOT / "Makefile").read_text(encoding="utf-8")


def test_readme_covers_the_required_topics():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needle in (
        "Interview Prep",
        "APP_NAME",
        "APP_EMOJI",
        "python -m streamlit run app.py",
        "LLM_MODEL",
        "PortAudio",
        "Docker",
        "pygame",
        "no model training",
    ):
        assert needle.lower() in readme.lower(), needle


def test_python_version_file_and_requirements():
    assert (ROOT / ".python-version").read_text().strip() == "3.11"
    dev = (ROOT / "requirements-dev.txt").read_text().split()
    assert {line.split("==")[0] for line in dev} == {"pytest", "ruff"}


@pytest.mark.parametrize("folder", ["inputs", "outputs", "audio"])
def test_empty_folders_are_kept_with_gitkeep(folder):
    assert (ROOT / folder / ".gitkeep").is_file()
    assert [p.name for p in (ROOT / folder).iterdir() if p.name != ".gitkeep"] == []


def test_required_files_exist():
    for name in (
        "app.py", "main.py", "schema.json", "requirements.txt", "requirements-dev.txt",
        "pyproject.toml", ".python-version", ".env.example", ".gitignore", "Dockerfile",
        "Makefile", "README.md", ".streamlit/config.toml", ".vscode/launch.json",
        ".vscode/settings.json", ".vscode/extensions.json", "utils/interview_flow.py",
    ):  # fmt: skip
        assert (ROOT / name).is_file(), name
    for module in (
        "analyze_candidate", "basic_details", "evaluation", "llm_call", "load_content",
        "prompts", "record_utils", "save_interview_data", "text_to_speech",
        "transcript_audio",
    ):  # fmt: skip
        assert (ROOT / "utils" / f"{module}.py").is_file(), module

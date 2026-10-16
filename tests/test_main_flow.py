"""The terminal version (main.py) with every device and service faked."""

import importlib
import json
from pathlib import Path

import pytest

import main
from utils import TranscriptionError


class Devices:
    """Fakes for recording, noise reduction, transcription and speech."""

    def __init__(self, monkeypatch, speech_works=True):
        self.spoken = []
        self.recorded = []
        self.transcribe_calls = 0
        self.fail_validation_times = 0
        self.speech_works = speech_works

        monkeypatch.setattr(main, "speak_text", self.speak_text)
        monkeypatch.setattr(main, "record_audio_with_interrupt", self.record)
        monkeypatch.setattr(main, "validate_audio_file", self.validate)
        monkeypatch.setattr(main, "reduce_noise", lambda filename, fs: filename)
        monkeypatch.setattr(main, "transcribe_with_speechmatics", self.transcribe)

    def speak_text(self, text, *args, **kwargs):
        self.spoken.append(text)
        return self.speech_works

    def record(self, filename="recorded.wav", fs=16000):
        self.recorded.append(filename)
        Path(filename).write_bytes(b"fake wav")
        return filename, fs

    def validate(self, filename):
        if self.fail_validation_times > 0:
            self.fail_validation_times -= 1
            return False
        return True

    def transcribe(self, path):
        self.transcribe_calls += 1
        return f"my answer {self.transcribe_calls}"


@pytest.fixture
def devices(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return Devices(monkeypatch)


@pytest.mark.parametrize("n", [1, 2, 5, 10])
def test_asks_exactly_n_questions(n, devices, fake_llm):
    fake = fake_llm()
    conversations = main.start_interview_with_ai("Jane Doe", "highlights", "jd", n)

    assert len(conversations) == n
    assert len(devices.recorded) == n
    assert devices.transcribe_calls == n
    assert len(devices.spoken) == n + 1  # N questions + the closing message
    assert fake.count("feedback") == n
    assert fake.count("question") == n - 1  # the last question gets feedback only
    assert [c["Candidate Answer"] for c in conversations] == [
        f"my answer {i}" for i in range(1, n + 1)
    ]


def test_audio_files_use_the_sanitized_name_and_question_numbers(devices, fake_llm):
    fake_llm()
    main.start_interview_with_ai("Jane / Doe", "highlights", "jd", 3)
    assert [Path(p) for p in devices.recorded] == [
        Path("audio") / "Jane_Doe" / f"Jane_Doe_{i}.wav" for i in (1, 2, 3)
    ]


def test_first_question_is_the_greeting_and_closing_is_one_of_the_templates(
    devices, fake_llm
):
    basic_details = importlib.import_module("utils.basic_details")

    fake_llm()
    main.start_interview_with_ai("Jane", "highlights", "jd", 2)

    greetings = [t("Jane", "Alex") for t in basic_details.ai_greeting_messages]
    closings = [t("Jane") for t in basic_details.final_thanks_for_taking_interview_msgs]
    assert devices.spoken[0] in greetings
    assert devices.spoken[1] == "Generated question 1"
    assert devices.spoken[-1] in closings


def test_runs_through_asyncio_run_without_unawaited_coroutines(
    devices, fake_llm, recwarn
):
    fake_llm()
    main.start_interview_with_ai("Jane", "highlights", "jd", 2)
    assert not [w for w in recwarn if "never awaited" in str(w.message)]


def test_missing_audio_playback_does_not_stop_the_interview(
    monkeypatch, tmp_path, fake_llm, capsys
):
    monkeypatch.chdir(tmp_path)
    Devices(monkeypatch, speech_works=False)
    fake_llm()
    conversations = main.start_interview_with_ai("Jane", "highlights", "jd", 2)
    assert len(conversations) == 2
    assert "Audio playback is not available" in capsys.readouterr().out


def test_bad_recording_is_retried(devices, fake_llm):
    fake_llm()
    devices.fail_validation_times = 1  # the first take is too quiet
    conversations = main.start_interview_with_ai("Jane", "highlights", "jd", 1)
    assert len(conversations) == 1
    assert len(devices.recorded) == 2
    assert devices.transcribe_calls == 1


def test_gives_up_after_three_bad_recordings(devices, fake_llm):
    fake_llm()
    devices.fail_validation_times = 99
    with pytest.raises(TranscriptionError):
        main.start_interview_with_ai("Jane", "highlights", "jd", 2)
    assert len(devices.recorded) == main.MAX_RECORDING_ATTEMPTS


def test_transcription_error_is_retried_not_used_as_the_answer(
    monkeypatch, tmp_path, fake_llm
):
    monkeypatch.chdir(tmp_path)
    devices = Devices(monkeypatch)
    attempts = {"n": 0}

    def flaky(path):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TranscriptionError("No speech detected in audio")
        return "a real answer"

    monkeypatch.setattr(main, "transcribe_with_speechmatics", flaky)
    fake_llm()
    conversations = main.start_interview_with_ai("Jane", "highlights", "jd", 1)
    assert conversations[0]["Candidate Answer"] == "a real answer"
    assert len(devices.recorded) == 2


# ---------------------------------------------------------------- app()
def setup_inputs(tmp_path):
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "resume.pdf").write_bytes(b"%PDF fake")
    (tmp_path / "inputs" / "job_description.txt").write_text("Backend engineer")


def test_app_end_to_end_with_fakes(monkeypatch, tmp_path, fake_llm):
    monkeypatch.chdir(tmp_path)
    setup_inputs(tmp_path)
    Devices(monkeypatch)
    fake_llm()
    monkeypatch.setattr(
        main,
        "load_content",
        lambda path: "resume text" if path.endswith(".pdf") else "Backend engineer",
    )
    monkeypatch.setattr("builtins.input", lambda *a: "y")

    assert main.app(max_questions=3) == 0

    saved = json.loads(
        (tmp_path / "outputs" / "Jane_Doe_interview_data.json").read_text()
    )
    assert saved["name"] == "Jane Doe"
    assert len(saved["conversations"]) == 3
    assert saved["overall_score"] == 8.0
    assert saved["job_description"] == "Backend engineer"


def test_app_can_be_cancelled(monkeypatch, tmp_path, fake_llm):
    monkeypatch.chdir(tmp_path)
    setup_inputs(tmp_path)
    devices = Devices(monkeypatch)
    fake_llm()
    monkeypatch.setattr(main, "load_content", lambda path: "text")
    monkeypatch.setattr("builtins.input", lambda *a: "n")

    assert main.app() == 0
    assert devices.spoken == []
    assert not (tmp_path / "outputs").exists()


def test_app_reports_missing_input_files(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    assert main.app() == 1
    assert "Resume file not found" in capsys.readouterr().out


def test_app_reports_errors_instead_of_crashing(
    monkeypatch, tmp_path, fake_llm, capsys
):
    monkeypatch.chdir(tmp_path)
    setup_inputs(tmp_path)
    Devices(monkeypatch)
    fake_llm(lambda prompt: "not json")
    monkeypatch.setattr(main, "load_content", lambda path: "text")
    monkeypatch.setattr("builtins.input", lambda *a: "y")

    assert main.app() == 1
    assert "Error" in capsys.readouterr().out


def test_command_line_arguments():
    assert main.parse_args([]).questions == 5
    assert main.parse_args(["--questions", "3"]).questions == 3
    with pytest.raises(SystemExit):
        main.parse_args(["--questions", "11"])
    with pytest.raises(SystemExit):
        main.parse_args(["--questions", "0"])


def test_main_has_no_unawaited_async_calls():
    """Bug 3: the original called async functions without await."""
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "asyncio.run(" in source

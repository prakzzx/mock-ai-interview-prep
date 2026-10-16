"""The Streamlit-free interview logic: counting, last-question rule, names, JSON."""

import asyncio
import json
import re
from pathlib import Path

import pytest

from utils.interview_flow import (
    InterviewFlow,
    InterviewFlowError,
    build_interview_data,
    evaluate_answer,
    get_answer_audio_path,
    sanitize_name,
)
from utils.save_interview_data import save_interview_data

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))


def run_full_interview(n):
    """Drive a whole interview exactly like app.py and main.py do."""
    flow = InterviewFlow(max_questions=n, current_question="Greeting question")
    banners = []
    asked = []
    while not flow.completed:
        banners.append(flow.progress_text)
        asked.append(flow.current_question)
        feedback, next_question = asyncio.run(
            evaluate_answer(
                flow.current_question,
                f"answer {flow.current_index}",
                "job description",
                "highlights",
                flow.is_last_question,
            )
        )
        flow.record_answer(f"answer {flow.current_index}", feedback, next_question)
    return flow, banners, asked


@pytest.mark.parametrize("n", [1, 2, 5, 10])
def test_exactly_n_questions_are_asked(n, fake_llm):
    fake_llm()
    flow, banners, asked = run_full_interview(n)

    assert len(asked) == n
    assert len(set(asked)) == n  # no question is repeated
    assert len(flow.conversations) == n
    assert flow.completed
    assert flow.current_index == n  # never runs past N


@pytest.mark.parametrize("n", [1, 2, 5, 10])
def test_last_question_gets_feedback_only(n, fake_llm):
    fake = fake_llm()
    flow, _, _ = run_full_interview(n)

    # N feedback calls, but only N-1 "next question" calls
    assert fake.count("feedback") == n
    assert fake.count("question") == n - 1
    # the very last LLM call of the interview is feedback, not a question
    from helpers import kind_of

    assert kind_of(fake.prompts[-1]) == "feedback"
    assert flow.conversations[-1]["Question"] == (
        "Greeting question" if n == 1 else f"Generated question {n - 1}"
    )


@pytest.mark.parametrize("n", [1, 2, 5, 10])
def test_progress_banner_is_always_correct(n, fake_llm):
    fake_llm()
    _, banners, _ = run_full_interview(n)
    assert banners == [f"Question {i} of {n}" for i in range(1, n + 1)]


def test_conversations_have_the_schema_keys_in_order(fake_llm):
    fake_llm()
    flow, _, _ = run_full_interview(3)
    expected_keys = list(SCHEMA["conversations"][0].keys())
    for conversation in flow.conversations:
        assert list(conversation.keys()) == expected_keys
        assert isinstance(conversation["Evaluation"], float)
    assert [c["Candidate Answer"] for c in flow.conversations] == [
        "answer 1",
        "answer 2",
        "answer 3",
    ]


def test_is_last_question_flag():
    flow = InterviewFlow(max_questions=2, current_question="Q1")
    assert not flow.is_last_question
    flow.record_answer("a", {"feedback": "f", "score": 5}, "Q2")
    assert flow.is_last_question
    assert flow.current_question == "Q2"


def test_record_answer_rules():
    flow = InterviewFlow(max_questions=2, current_question="Q1")
    with pytest.raises(InterviewFlowError):  # next question required
        flow.record_answer("a", {"feedback": "f", "score": 5}, None)
    with pytest.raises(InterviewFlowError):
        flow.record_answer("a", {"feedback": "f", "score": 5}, "")
    assert flow.conversations == []  # failed calls change nothing
    assert flow.current_index == 1

    flow.record_answer("a", {"feedback": "f", "score": 5}, "Q2")
    with pytest.raises(InterviewFlowError):  # last question has no next question
        flow.record_answer("b", {"feedback": "f", "score": 5}, "Q3")
    flow.record_answer("b", {"feedback": "f", "score": 5}, None)
    assert flow.completed
    with pytest.raises(InterviewFlowError):  # already finished
        flow.record_answer("c", {"feedback": "f", "score": 5}, None)
    assert len(flow.conversations) == 2


def test_record_answer_coerces_scores():
    flow = InterviewFlow(max_questions=1, current_question="Q1")
    flow.record_answer("a", {"feedback": "f", "score": "99"}, None)
    assert flow.conversations[0]["Evaluation"] == 10.0


def test_record_answer_rejects_an_unusable_score():
    flow = InterviewFlow(max_questions=1, current_question="Q1")
    with pytest.raises(ValueError):
        flow.record_answer("a", {"feedback": "f", "score": "n/a"}, None)
    assert not flow.completed


@pytest.mark.parametrize("bad", [0, -1, "5", None, True, 2.5])
def test_invalid_max_questions(bad):
    with pytest.raises(ValueError):
        InterviewFlow(max_questions=bad, current_question="Q1")


def test_empty_first_question_is_rejected():
    with pytest.raises(ValueError):
        InterviewFlow(max_questions=3, current_question="")


# ---------------------------------------------------------------- sanitize_name
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Jane Doe", "Jane_Doe"),
        ("  Mary   Ann  ", "Mary_Ann"),
        ('a/b\\c:d*e?f"g<h>i|j', "abcdefghij"),
        ("../../etc/passwd", "etcpasswd"),
        ("..\\..\\Windows\\System32", "WindowsSystem32"),
        (".hidden", "hidden"),
        ("José Müller", "José_Müller"),
        ("O'Brien, Pat", "O'Brien,_Pat"),
        ("CON", "_CON"),
        ("nul.txt", "_nul.txt"),
        ("", "candidate"),
        ("???", "candidate"),
        ("   ", "candidate"),
        (None, "candidate"),
        ("tab\tname\nnewline", "tab_name_newline"),
    ],
)
def test_sanitize_name(raw, expected):
    assert sanitize_name(raw) == expected


@pytest.mark.parametrize("raw", ["../../x", "a/b", "C:\\evil", "x|y", "q?*<>"])
def test_sanitized_names_contain_no_path_characters(raw):
    safe = sanitize_name(raw)
    assert not re.search(r'[/\\:*?"<>| ]', safe)
    assert ".." not in safe


def test_audio_path_uses_the_sanitized_name():
    path = get_answer_audio_path("Jane / Doe", 3)
    assert Path(path) == Path("audio") / "Jane_Doe" / "Jane_Doe_3.wav"
    custom = get_answer_audio_path("Jane Doe", 1, root="somewhere")
    assert Path(custom) == Path("somewhere/Jane_Doe/Jane_Doe_1.wav")


# ---------------------------------------------------------------- JSON output
def sample_conversations():
    return [
        {
            "Question": "Q1",
            "Candidate Answer": "A1",
            "Evaluation": 8.0,
            "Feedback": "F1",
        },
        {
            "Question": "Q2",
            "Candidate Answer": "A2",
            "Evaluation": 7.0,
            "Feedback": "F2",
        },
        {
            "Question": "Q3",
            "Candidate Answer": "A3",
            "Evaluation": 7.0,
            "Feedback": "F3",
        },
    ]


def test_interview_data_matches_the_schema_keys():
    data = build_interview_data(
        "Jane Doe", "JD text", "HL text", sample_conversations()
    )
    # schema.json also lists "next_hash"; the original app never wrote it and the
    # requested key list does not include it, so it is the one documented difference.
    expected = set(SCHEMA) - {"next_hash"}
    assert set(data) == expected
    assert list(data["conversations"][0]) == list(SCHEMA["conversations"][0])
    assert data["name"] == "Jane Doe"
    assert data["id"] == 1
    assert data["job_description"] == "JD text"
    assert data["resume_highlights"] == "HL text"
    assert data["overall_score"] == 7.33  # (8 + 7 + 7) / 3 rounded to 2 decimals
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
    assert re.match(pattern, data["createdAt"])
    assert data["createdAt"] == data["updatedAt"]
    assert re.match(pattern, SCHEMA["createdAt"])  # same format as the schema example


def test_save_interview_data_writes_the_json_file(tmp_path):
    data = build_interview_data("Jane / Doe", "JD", "HL", sample_conversations())
    out_dir = tmp_path / "outputs"
    path = save_interview_data(data, "Jane / Doe", output_dir=str(out_dir))

    assert Path(path) == out_dir / "Jane_Doe_interview_data.json"
    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    assert saved["name"] == "Jane / Doe"  # the real name is kept inside the JSON
    assert set(saved) == set(SCHEMA) - {"next_hash"}
    assert len(saved["conversations"]) == 3


def test_save_interview_data_keeps_non_ascii_names_readable(tmp_path):
    data = build_interview_data("José Müller", "JD", "HL", sample_conversations())
    path = save_interview_data(data, "José Müller", output_dir=str(tmp_path))
    assert "José Müller" in Path(path).read_text(encoding="utf-8")


def test_full_interview_produces_a_valid_record(fake_llm, tmp_path):
    fake_llm()
    flow, _, _ = run_full_interview(5)
    data = build_interview_data("Jane Doe", "JD", "HL", flow.conversations)
    assert len(data["conversations"]) == 5
    assert data["overall_score"] == 8.0

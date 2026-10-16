"""Streamlit smoke tests with streamlit.testing.v1.AppTest (no browser, no network)."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import utils
from utils import InterviewFlow

ROOT = Path(__file__).resolve().parent.parent
APP_FILE = str(ROOT / "app.py")
OLD_TITLE = "AI Interview" + " System"
OLD_EMOJI = "\U0001f916"


def new_app():
    return AppTest.from_file(APP_FILE, default_timeout=60)


def texts(elements):
    return [element.value for element in elements]


@pytest.fixture(autouse=True)
def in_tmp_dir(tmp_path, monkeypatch):
    """The app writes audio/ and outputs/ relative to the working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def started_state(at, flow, messages=None, spoken=True):
    at.session_state["name"] = "Jane Doe"
    at.session_state["resume_highlights"] = "Led a team"
    at.session_state["job_description"] = "Backend role"
    at.session_state["interview_started"] = True
    at.session_state["flow"] = flow
    at.session_state["messages"] = messages or [
        {"role": "assistant", "content": flow.current_question}
    ]
    at.session_state["question_spoken"] = spoken
    at.session_state["awaiting_response"] = spoken


# ---------------------------------------------------------------- first render
def test_first_render_has_no_exception_and_the_right_title():
    at = new_app().run()
    assert not at.exception
    main_title = at.main.title[0].value
    assert "Interview Prep" in main_title
    assert "🎤" in main_title
    assert OLD_TITLE not in main_title
    assert not any(OLD_TITLE in value for value in texts(at.title))
    assert not any(
        OLD_TITLE in value or OLD_EMOJI in value for value in texts(at.markdown)
    )


def test_instructions_are_shown_before_the_interview_starts():
    at = new_app().run()
    body = " ".join(texts(at.markdown))
    assert "Interview Prep" in body
    assert "Upload Resume" in body and "Review Results" in body


def test_sidebar_has_all_the_inputs():
    at = new_app().run()
    sidebar = at.sidebar
    assert [e.label for e in sidebar.get("file_uploader")] == [
        "Upload your Resume (PDF)"
    ]
    assert [e.label for e in sidebar.text_area] == ["Paste the Job Description"]

    number = sidebar.number_input[0]
    assert number.label == "Maximum number of questions"
    assert (number.min, number.max, number.value) == (1, 10, 5)

    radio = sidebar.radio[0]
    assert radio.label == "Select AI Interviewer Voice"
    assert list(radio.options) == [
        "Alex (Male)",
        "Aria (Female)",
        "Natasha (Female)",
        "Sonia (Female)",
    ]
    assert radio.value == "Alex (Male)"

    assert [b.label for b in sidebar.button] == ["Submit"]


def test_the_theme_css_is_injected_without_external_assets():
    at = new_app().run()
    css_blocks = [v for v in texts(at.markdown) if "<style>" in v]
    assert len(css_blocks) == 1
    assert "#FFE6F0" in css_blocks[0]
    assert "http" not in css_blocks[0]


def test_submit_without_inputs_shows_a_warning_and_nothing_else():
    at = new_app().run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert any("upload your resume" in w.value.lower() for w in at.warning)
    assert not at.button or all(b.label != "Start Interview" for b in at.button)


# ---------------------------------------------------------------- resume step
def test_submitted_resume_shows_the_candidate_name_and_start_button():
    at = new_app()
    at.session_state["name"] = "Jane Doe"
    at.session_state["resume_highlights"] = "Led a team"
    at.run()
    assert not at.exception
    assert "Candidate Name: Jane Doe" in texts(at.success)
    assert "Start Interview" in [b.label for b in at.button]


def test_start_interview_asks_the_first_question(monkeypatch):
    spoken = []
    monkeypatch.setattr(
        utils, "speak_text", lambda text, **kw: spoken.append((text, kw)) or True
    )

    at = new_app()
    at.session_state["name"] = "Jane Doe"
    at.session_state["resume_highlights"] = "Led a team"
    at.session_state["job_description"] = "Backend role"
    at.run()
    at.sidebar.number_input[0].set_value(3)
    at.sidebar.radio[0].set_value("Sonia (Female)")
    at.run()
    [b for b in at.button if b.label == "Start Interview"][0].click().run()

    assert not at.exception
    flow = at.session_state["flow"]
    assert flow.max_questions == 3
    assert "Question 1 of 3" in " ".join(texts(at.markdown))
    assert "My name is Sonia" in flow.current_question
    assert len(at.chat_message) == 1
    assert spoken and spoken[0][1]["voice"] == "en-GB-SoniaNeural"
    assert at.session_state["awaiting_response"] is True


# ---------------------------------------------------------------- interview screen
def test_progress_banner_and_chat_in_the_middle_of_the_interview():
    at = new_app()
    flow = InterviewFlow(
        max_questions=5, current_question="Second question?", current_index=2
    )
    started_state(
        at,
        flow,
        messages=[
            {"role": "assistant", "content": "Hello, first question"},
            {"role": "user", "content": "my first answer"},
            {"role": "assistant", "content": "Second question?"},
        ],
    )
    at.run()
    assert not at.exception
    banners = [v for v in texts(at.markdown) if 'class="interview-progress"' in v]
    assert len(banners) == 1 and "Question 2 of 5" in banners[0]
    assert len(at.chat_message) == 3
    assert [c.name for c in at.chat_message] == ["assistant", "user", "assistant"]
    assert not at.warning


def test_banner_on_the_last_question():
    at = new_app()
    started_state(
        at, InterviewFlow(max_questions=3, current_question="Last?", current_index=3)
    )
    at.run()
    banner = [v for v in texts(at.markdown) if 'class="interview-progress"' in v][0]
    assert "Question 3 of 3" in banner


def test_question_is_spoken_with_the_chosen_voice(monkeypatch):
    spoken = []
    monkeypatch.setattr(
        utils, "speak_text", lambda text, **kw: spoken.append((text, kw)) or True
    )
    at = new_app()
    started_state(
        at,
        InterviewFlow(max_questions=2, current_question="Why this role?"),
        spoken=False,
    )
    at.run()
    assert not at.exception
    assert spoken == [("Why this role?", {"voice": "en-US-GuyNeural"})]
    assert at.session_state["question_spoken"] is True
    assert at.session_state["awaiting_response"] is True
    assert not at.warning


def test_failed_audio_playback_shows_a_warning_with_the_question(monkeypatch):
    monkeypatch.setattr(utils, "speak_text", lambda text, **kw: False)
    at = new_app()
    started_state(
        at,
        InterviewFlow(max_questions=2, current_question="Why this role?"),
        spoken=False,
    )
    at.run()
    assert not at.exception
    assert any("Why this role?" in w.value for w in at.warning)
    assert at.session_state["awaiting_response"] is True  # the interview goes on


def test_a_recording_error_is_shown_and_the_user_can_try_again():
    at = new_app()
    started_state(at, InterviewFlow(max_questions=2, current_question="Q?"))
    at.session_state["answer_error"] = (
        "Could not process your answer: No speech detected."
    )
    at.run()
    assert not at.exception
    assert any("No speech detected" in e.value for e in at.error)
    assert at.session_state["processing_audio"] is False


# ---------------------------------------------------------------- final results
def completed_flow(n=3):
    flow = InterviewFlow(max_questions=n, current_question="Q1")
    for i in range(1, n + 1):
        flow.record_answer(
            f"answer {i}",
            {"feedback": f"feedback {i}", "score": 6 + i},
            None if i == n else f"Q{i + 1}",
        )
    return flow


def test_final_results_screen_and_saved_json(in_tmp_dir, monkeypatch):
    spoken = []
    monkeypatch.setattr(
        utils, "speak_text", lambda text, **kw: spoken.append(text) or True
    )
    at = new_app()
    flow = completed_flow(3)  # scores 7, 8, 9 -> overall 8.00
    started_state(at, flow)
    at.run()  # interview finished: the closing message is prepared and spoken
    assert not at.exception

    assert at.session_state["thanks_message_prepared"] is True
    assert at.session_state["show_final_results"] is True
    assert len(spoken) == 1  # the closing message was spoken once

    body = " ".join(texts(at.markdown))
    assert "**Overall Score:** 8.00/10" in body
    assert "**Candidate:** Jane Doe" in body
    assert len(at.expander) == 3
    assert at.expander[0].label == "Question 1 (Score: 7/10)"
    assert "Start New Interview" in [b.label for b in at.button]

    saved = json.loads(
        (in_tmp_dir / "outputs" / "Jane_Doe_interview_data.json").read_text()
    )
    assert saved["name"] == "Jane Doe"
    assert saved["overall_score"] == 8.0
    assert len(saved["conversations"]) == 3
    assert set(saved) == {
        "name", "createdAt", "updatedAt", "id", "job_description",
        "resume_highlights", "conversations", "overall_score",
    }  # fmt: skip


def test_start_new_interview_resets_everything(monkeypatch):
    monkeypatch.setattr(utils, "speak_text", lambda text, **kw: True)
    at = new_app()
    started_state(at, completed_flow(2))
    at.run()
    [b for b in at.button if b.label == "Start New Interview"][0].click().run()

    assert not at.exception
    assert at.session_state["name"] == ""
    assert at.session_state["flow"] is None
    assert at.session_state["interview_started"] is False
    assert at.session_state["messages"] == []
    # AppTest returns the pre-rerun tree after a widget-triggered st.rerun(); one more
    # run shows the page the browser displays after the reset.
    at.run()
    assert not at.exception
    assert not at.expander
    assert "Upload Resume" in " ".join(texts(at.markdown))  # instructions are back

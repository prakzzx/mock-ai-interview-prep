"""The prompts, templates and voices must be exactly the originals (no training here:
all behavior comes from these three prompts and the message templates)."""

import hashlib
import importlib
import os
import re
import zipfile
from pathlib import Path

import pytest

import app

from utils import prompts

bd = importlib.import_module("utils.basic_details")  # not the prompt string

ROOT = Path(__file__).resolve().parent.parent

# SHA-256 of the original files, computed from AI-Interview-System-main.zip
ORIGINAL_SHA256 = {
    "utils/prompts.py": "5239d0307fb681463e1e48eecddf4dccd58390e5b9a0c6d41ff96d145edd1d45",
    "requirements.txt": "b9702a3a4673414166cc399d4bc758d8890087a54adf8734d8b2693d584d5a93",
    "schema.json": "74cad5a19c2fc618b3c983122471aa8f19e3de970e4748159a0445c799bdeab9",
    ".env.example": "ecd2a7b3f8e5ac78dbbac1a4de9023ad260fdd1c5d141367ee9a3c91f40f015e",
    ".python-version": "49a506dd32096b010d75205acf3430c9ae6c40351888129499e5a5e487126c93",
}


@pytest.mark.parametrize("relative_path", sorted(ORIGINAL_SHA256))
def test_verbatim_files_match_the_original_hash(relative_path):
    actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
    assert actual == ORIGINAL_SHA256[relative_path]


ORIGINAL_ZIP = os.environ.get("ORIGINAL_ZIP")


@pytest.mark.skipif(
    not ORIGINAL_ZIP, reason="set ORIGINAL_ZIP to the original zip path"
)
@pytest.mark.parametrize(
    "relative_path",
    ["utils/prompts.py", "requirements.txt", "schema.json", ".env.example"],
)
def test_verbatim_files_match_the_attached_zip(relative_path):
    with zipfile.ZipFile(ORIGINAL_ZIP) as archive:
        prefix = archive.namelist()[0].split("/")[0]
        original = archive.read(f"{prefix}/{relative_path}")
    assert (ROOT / relative_path).read_bytes() == original


@pytest.mark.skipif(
    not ORIGINAL_ZIP, reason="set ORIGINAL_ZIP to the original zip path"
)
def test_message_templates_match_the_attached_zip_byte_for_byte():
    with zipfile.ZipFile(ORIGINAL_ZIP) as archive:
        prefix = archive.namelist()[0].split("/")[0]
        original = archive.read(f"{prefix}/utils/basic_details.py").decode("utf-8")
    marker = "ai_greeting_messages = ["
    current = (ROOT / "utils" / "basic_details.py").read_text(encoding="utf-8")
    assert current[current.index(marker) :] == original[original.index(marker) :]


def test_prompts_keep_their_key_instructions():
    assert "Make sure to complete with in 90 words." in prompts.feedback_generation
    for line in (
        "9-10: Exceptional response that exceeds expectations",
        "7-8: Strong response that meets most requirements effectively",
        "5-6: Adequate response with some gaps or missed opportunities",
        "3-4: Below average response with significant areas for improvement",
        "1-2: Poor response that fails to address the question adequately",
        "Scoring Guidelines (1-10 scale):",
    ):
        assert line in prompts.feedback_generation
    assert "Identify and extract the 5-7 most compelling" in prompts.basic_details
    assert '"next_question"' in prompts.next_question_generation
    assert '"score": <Numerical score from 1-10' in prompts.feedback_generation
    assert '"resume_highlights"' in prompts.basic_details


def test_prompt_placeholders():
    def placeholders(template):
        return set(re.findall(r"(?<!\{)\{(\w+)\}(?!\})", template))

    assert placeholders(prompts.basic_details) == {"resume_content"}
    assert placeholders(prompts.next_question_generation) == {
        "previous_question",
        "candidate_response",
        "job_description",
        "resume_highlights",
    }
    assert placeholders(prompts.feedback_generation) == {
        "question",
        "candidate_response",
        "job_description",
        "resume_highlights",
    }


def test_prompts_can_be_formatted_with_braces_in_the_input():
    text = prompts.basic_details.format(resume_content="Skills: {Python} {{x}}")
    assert "Skills: {Python} {{x}}" in text
    assert '"name": "<Full name' in text  # doubled braces became JSON braces


GREETING_START = (
    "Hi {name}, welcome to this AI interview! My name is {who} and I'll be your "
    "interviewer today. Let's get started!\n\n"
)
GREETING_QUESTIONS = [
    "Can you tell me a bit about yourself and what you're looking for in a job?",
    "Can you give me a quick overview of your background and experience?",
    "Can you tell me a little bit about your goals and aspirations?",
    "Can you briefly introduce yourself and tell me about your achievements and skills?",
]
CLOSINGS = [
    "Thanks for taking the time to chat today, {name}. I really enjoyed our conversation. Wishing you all the best in your career!",
    "It was great speaking with you, {name}. I hope the interview was a valuable experience for you. Good luck moving forward!",
    "Appreciate your time today, {name}. Best of luck with the rest of your job applications and interviews!",
    "Thank you for the engaging conversation, {name}. I wish you success in your job hunt and future endeavors!",
    "It was a pleasure talking to you, {name}. I hope the interview helped clarify your goals. All the best!",
    "Thanks again for your time, {name}. I hope you found the interview insightful. Good luck on your journey ahead!",
]


def test_four_greeting_templates_are_unchanged():
    assert len(bd.ai_greeting_messages) == 4
    for template, question in zip(
        bd.ai_greeting_messages, GREETING_QUESTIONS, strict=True
    ):
        expected = GREETING_START.format(name="Jane", who="Sonia") + question
        assert template("Jane", "Sonia") == expected


def test_six_closing_templates_are_unchanged():
    assert len(bd.final_thanks_for_taking_interview_msgs) == 6
    for template, expected in zip(
        bd.final_thanks_for_taking_interview_msgs, CLOSINGS, strict=True
    ):
        assert template("Jane") == expected.format(name="Jane")


def test_random_selection_covers_the_templates(monkeypatch):
    seen_greetings = {bd.get_ai_greeting_message("Jane", "Alex") for _ in range(300)}
    seen_closings = {bd.get_final_thanks_message("Jane") for _ in range(300)}
    assert seen_greetings == {
        GREETING_START.format(name="Jane", who="Alex") + q for q in GREETING_QUESTIONS
    }
    assert seen_closings == {c.format(name="Jane") for c in CLOSINGS}


def test_default_interviewer_name_is_alex():
    assert "My name is Alex" in bd.get_ai_greeting_message("Jane")


def test_four_voices_are_unchanged():
    assert app.get_ai_voice_details() == {
        "Alex (Male)": {"name": "Alex", "code": "en-US-GuyNeural"},
        "Aria (Female)": {"name": "Aria", "code": "en-US-AriaNeural"},
        "Natasha (Female)": {"name": "Natasha", "code": "en-AU-NatashaNeural"},
        "Sonia (Female)": {"name": "Sonia", "code": "en-GB-SoniaNeural"},
    }


def test_resume_extraction_uses_the_basic_details_prompt(fake_llm):
    fake = fake_llm()
    name, highlights = bd.extract_resume_info_using_llm("MY RESUME TEXT")
    assert (name, highlights) == ("Jane Doe", "Led a team of 5 engineers.")
    assert "MY RESUME TEXT" in fake.prompts[0]
    assert "expert resume parser" in fake.prompts[0]


def test_resume_extraction_accepts_list_highlights(fake_llm):
    fake_llm(lambda p: '{"name": " Jane ", "resume_highlights": ["One", "Two"]}')
    assert bd.extract_resume_info_using_llm("x") == ("Jane", "One\nTwo")


def test_resume_extraction_tolerates_the_trailing_comma_from_the_template(fake_llm):
    fake_llm(lambda p: '{"name": "Jane", "resume_highlights": "Great work",\n}')
    assert bd.extract_resume_info_using_llm("x") == ("Jane", "Great work")


@pytest.mark.parametrize(
    "reply",
    [
        '{"resume_highlights": "x"}',
        '{"name": "", "resume_highlights": "x"}',
        '{"name": "Jane"}',
        '{"name": 5, "resume_highlights": "x"}',
    ],
)
def test_resume_extraction_rejects_incomplete_answers(fake_llm, reply):
    fake_llm(lambda p: reply)
    with pytest.raises(bd.ResumeInfoError):
        bd.extract_resume_info_using_llm("x")

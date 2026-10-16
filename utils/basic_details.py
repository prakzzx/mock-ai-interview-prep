import random

from utils.llm_call import get_json_from_llm
from utils.prompts import basic_details


class ResumeInfoError(Exception):
    """Raised when the LLM does not return usable resume information."""


def extract_resume_info_using_llm(resume_content):
    """Use the LLM (basic_details prompt) to extract the candidate name and highlights."""
    final_prompt = basic_details.format(resume_content=resume_content)
    response = get_json_from_llm(final_prompt)

    name = response.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ResumeInfoError("The LLM response did not contain a candidate name.")

    highlights = response.get("resume_highlights", "")
    if isinstance(highlights, (list, tuple)):
        highlights = "\n".join(str(item) for item in highlights)
    elif not isinstance(highlights, str):
        highlights = str(highlights)
    if not highlights.strip():
        raise ResumeInfoError("The LLM response did not contain resume highlights.")

    return name.strip(), highlights.strip()


ai_greeting_messages = [
    lambda name, interviewer_name: f"Hi {name}, welcome to this AI interview! My name is {interviewer_name} and I'll be your interviewer today. Let's get started!\n\nCan you tell me a bit about yourself and what you're looking for in a job?",
    lambda name, interviewer_name: f"Hi {name}, welcome to this AI interview! My name is {interviewer_name} and I'll be your interviewer today. Let's get started!\n\nCan you give me a quick overview of your background and experience?",
    lambda name, interviewer_name: f"Hi {name}, welcome to this AI interview! My name is {interviewer_name} and I'll be your interviewer today. Let's get started!\n\nCan you tell me a little bit about your goals and aspirations?",
    lambda name, interviewer_name: f"Hi {name}, welcome to this AI interview! My name is {interviewer_name} and I'll be your interviewer today. Let's get started!\n\nCan you briefly introduce yourself and tell me about your achievements and skills?",
]


final_thanks_for_taking_interview_msgs = [
    lambda name: f"Thanks for taking the time to chat today, {name}. I really enjoyed our conversation. Wishing you all the best in your career!",
    lambda name: f"It was great speaking with you, {name}. I hope the interview was a valuable experience for you. Good luck moving forward!",
    lambda name: f"Appreciate your time today, {name}. Best of luck with the rest of your job applications and interviews!",
    lambda name: f"Thank you for the engaging conversation, {name}. I wish you success in your job hunt and future endeavors!",
    lambda name: f"It was a pleasure talking to you, {name}. I hope the interview helped clarify your goals. All the best!",
    lambda name: f"Thanks again for your time, {name}. I hope you found the interview insightful. Good luck on your journey ahead!",
]


def get_ai_greeting_message(name, interviewer_name="Alex"):
    return random.choice(ai_greeting_messages)(name, interviewer_name)


def get_final_thanks_message(name):
    return random.choice(final_thanks_for_taking_interview_msgs)(name)

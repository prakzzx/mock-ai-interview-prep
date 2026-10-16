"""
Streamlit-free interview logic.

Everything that decides *how* the interview progresses lives here so it can be unit
tested without a browser: question counting, the "last question gets feedback only"
rule, concurrent LLM analysis, file-name sanitizing and the saved-JSON structure.
app.py (web) and main.py (terminal) are thin layers on top of this module.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.analyze_candidate import (
    analyze_candidate_response_and_generate_new_question,
    get_feedback_of_candidate_response,
)
from utils.evaluation import coerce_score, get_overall_evaluation_score

MIN_QUESTIONS = 1
MAX_QUESTIONS_LIMIT = 10
DEFAULT_MAX_QUESTIONS = 5
ANALYSIS_TIMEOUT_SECONDS = 30.0


class InterviewFlowError(Exception):
    """Raised when the interview flow is used in an invalid way."""


@dataclass
class InterviewFlow:
    """
    Tracks one interview of exactly `max_questions` questions.

    `current_index` is the 1-based number of the question being asked right now. The
    first question is the greeting message. When the answer to the last question is
    recorded, `completed` becomes True and the index stays at `max_questions`.
    """

    max_questions: int
    current_question: str
    current_index: int = 1
    conversations: List[Dict[str, Any]] = field(default_factory=list)
    completed: bool = False

    def __post_init__(self):
        if isinstance(self.max_questions, bool) or not isinstance(
            self.max_questions, int
        ):
            raise ValueError("max_questions must be an integer")
        if self.max_questions < MIN_QUESTIONS:
            raise ValueError(f"max_questions must be at least {MIN_QUESTIONS}")
        if not self.current_question:
            raise ValueError("current_question must not be empty")

    @property
    def is_last_question(self) -> bool:
        return self.current_index >= self.max_questions

    @property
    def progress_text(self) -> str:
        return f"Question {self.current_index} of {self.max_questions}"

    def record_answer(
        self,
        answer: str,
        feedback: Dict[str, Any],
        next_question: Optional[str] = None,
    ) -> None:
        """
        Store the answer to the current question and move on.

        For every question except the last, `next_question` is required. For the last
        question it must be None: the interview is then marked completed.
        """
        if self.completed:
            raise InterviewFlowError("The interview is already completed.")

        last = self.is_last_question
        if last and next_question is not None:
            raise InterviewFlowError("The last question must not have a next question.")
        if not last and not next_question:
            raise InterviewFlowError("A next question is required before the last one.")

        self.conversations.append(
            {
                "Question": self.current_question,
                "Candidate Answer": answer,
                "Evaluation": coerce_score(feedback.get("score")),
                "Feedback": str(feedback.get("feedback", "")),
            }
        )

        if last:
            self.completed = True
        else:
            self.current_index += 1
            self.current_question = next_question


async def evaluate_answer(
    question: str,
    answer: str,
    job_description: str,
    resume_highlights: str,
    is_last_question: bool,
    timeout: float = ANALYSIS_TIMEOUT_SECONDS,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Run the LLM analysis for one answer.

    Returns (feedback, next_question). For the last question only feedback is requested
    and next_question is None; otherwise feedback and next question are requested
    concurrently.

    Raises:
        InterviewAnalysisError: if the LLM output is unusable.
        asyncio.TimeoutError: if the LLM takes longer than `timeout` seconds.
    """
    if is_last_question:
        feedback = await asyncio.wait_for(
            get_feedback_of_candidate_response(
                question, answer, job_description, resume_highlights
            ),
            timeout=timeout,
        )
        return feedback, None

    next_question, feedback = (
        await analyze_candidate_response_and_generate_new_question(
            question, answer, job_description, resume_highlights, timeout=timeout
        )
    )
    return feedback, next_question


# Whitespace control characters (tab, newline, ...) are left for the \s+ step below.
_UNSAFE_PATH_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x08\x0e-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}  # fmt: skip


def sanitize_name(name: str, fallback: str = "candidate") -> str:
    """
    Make a candidate name safe to use in file and folder names.

    Removes / \\ : * ? " < > | and control characters, turns whitespace into
    underscores and strips leading/trailing dots and underscores. The real name is kept
    for display and JSON; only paths use this value.
    """
    cleaned = _UNSAFE_PATH_CHARS.sub("", str(name or ""))
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.replace("..", "")
    cleaned = cleaned.strip("._")
    if not cleaned:
        return fallback
    if cleaned.split(".")[0].upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned


def get_answer_audio_path(name: str, question_number: int, root: str = "audio") -> str:
    """Path audio/<name>/<name>_<n>.wav using the sanitized name."""
    safe = sanitize_name(name)
    return str(Path(root) / safe / f"{safe}_{question_number}.wav")


def utc_timestamp() -> str:
    """Timestamp like 2023-05-22T11:00:00.000Z (the format used in schema.json)."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def build_interview_data(
    name: str,
    job_description: str,
    resume_highlights: str,
    conversations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the record saved to outputs/<name>_interview_data.json."""
    now = utc_timestamp()
    return {
        "name": name,
        "createdAt": now,
        "updatedAt": now,
        "id": 1,
        "job_description": job_description,
        "resume_highlights": resume_highlights,
        "conversations": conversations,
        "overall_score": round(get_overall_evaluation_score(conversations), 2),
    }

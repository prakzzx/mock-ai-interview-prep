import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Tuple

from utils.evaluation import coerce_score
from utils.llm_call import get_json_from_llm
from utils.prompts import feedback_generation, next_question_generation

# Thread pool for the blocking LLM calls
executor = ThreadPoolExecutor(max_workers=4)


class InterviewAnalysisError(Exception):
    """Custom exception for interview analysis errors"""


async def _make_llm_call_async(prompt: str) -> Dict[str, Any]:
    """
    Make the LLM call (with JSON parsing and one retry) in a thread pool so that
    several calls can run concurrently.
    """
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, get_json_from_llm, prompt)
    except Exception as e:
        raise InterviewAnalysisError(f"Failed to get LLM response: {str(e)}") from e


async def get_next_question(
    previous_question: str,
    candidate_response: str,
    resume_highlights: str,
    job_description: str,
) -> str:
    """
    Generate next interview question based on previous interaction

    Args:
        previous_question: The previous question asked
        candidate_response: Candidate's response to previous question
        resume_highlights: Key highlights from candidate's resume
        job_description: Job description/requirements

    Returns:
        str: Next question to ask

    Raises:
        InterviewAnalysisError: If question generation fails
    """
    try:
        final_prompt = next_question_generation.format(
            previous_question=previous_question,
            candidate_response=candidate_response,
            resume_highlights=resume_highlights,
            job_description=job_description,
        )

        response = await _make_llm_call_async(final_prompt)

        next_question = response.get("next_question")
        if not isinstance(next_question, str) or not next_question.strip():
            raise InterviewAnalysisError("Missing 'next_question' in LLM response")

        return next_question.strip()

    except InterviewAnalysisError:
        raise
    except Exception as e:
        raise InterviewAnalysisError(f"Question generation failed: {str(e)}") from e


async def get_feedback_of_candidate_response(
    question: str,
    candidate_response: str,
    job_description: str,
    resume_highlights: str,
) -> Dict[str, Any]:
    """
    Generate feedback for candidate's response

    Args:
        question: The question that was asked
        candidate_response: Candidate's response
        job_description: Job description/requirements
        resume_highlights: Key highlights from candidate's resume

    Returns:
        Dict containing feedback (str) and score (float clamped to 0-10)

    Raises:
        InterviewAnalysisError: If feedback generation fails
    """
    try:
        final_prompt = feedback_generation.format(
            question=question,
            candidate_response=candidate_response,
            job_description=job_description,
            resume_highlights=resume_highlights,
        )

        response = await _make_llm_call_async(final_prompt)

        # Validate response structure
        required_fields = ["feedback", "score"]
        missing_fields = [field for field in required_fields if field not in response]
        if missing_fields:
            raise InterviewAnalysisError(
                f"Missing fields in response: {missing_fields}"
            )

        try:
            score = coerce_score(response["score"])
        except ValueError as e:
            raise InterviewAnalysisError(
                f"Invalid score format: {response['score']}"
            ) from e

        return {"feedback": str(response["feedback"]).strip(), "score": score}

    except InterviewAnalysisError:
        raise
    except Exception as e:
        raise InterviewAnalysisError(f"Feedback generation failed: {str(e)}") from e


async def analyze_candidate_response_and_generate_new_question(
    question: str,
    candidate_response: str,
    job_description: str,
    resume_highlights: str,
    timeout: float = 30.0,
) -> Tuple[str, Dict[str, Any]]:
    """
    Analyze candidate response and generate next question concurrently

    Args:
        question: The question that was asked
        candidate_response: Candidate's response
        job_description: Job description/requirements
        resume_highlights: Key highlights from candidate's resume
        timeout: Maximum time to wait for both operations

    Returns:
        Tuple of (next_question, feedback_dict)

    Raises:
        InterviewAnalysisError: If analysis fails
        asyncio.TimeoutError: If operations exceed timeout
    """
    try:
        # Run both operations concurrently for better performance
        feedback_task = get_feedback_of_candidate_response(
            question, candidate_response, job_description, resume_highlights
        )

        next_question_task = get_next_question(
            question, candidate_response, resume_highlights, job_description
        )

        # Wait for both with timeout
        feedback, next_question = await asyncio.wait_for(
            asyncio.gather(feedback_task, next_question_task), timeout=timeout
        )
        return next_question, feedback
    except asyncio.TimeoutError:
        raise
    except InterviewAnalysisError:
        raise
    except Exception as e:
        raise InterviewAnalysisError(f"Response analysis failed: {str(e)}") from e

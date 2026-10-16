"""Concurrent analysis against a fake LLM: concurrency, timeout and error handling."""

import asyncio
import json
import threading
import time

import pytest

from helpers import kind_of
from utils.analyze_candidate import (
    InterviewAnalysisError,
    analyze_candidate_response_and_generate_new_question,
    get_feedback_of_candidate_response,
    get_next_question,
)
from utils.interview_flow import evaluate_answer

ARGS = ("Tell me about yourself", "I am an engineer", "Backend role", "Led a team")


def run(coro):
    return asyncio.run(coro)


def test_returns_next_question_and_feedback(fake_llm):
    fake = fake_llm()
    next_question, feedback = run(
        analyze_candidate_response_and_generate_new_question(*ARGS)
    )
    assert next_question == "Generated question 1"
    assert feedback == {"feedback": "Good answer.", "score": 8.0}
    assert fake.count("feedback") == 1
    assert fake.count("question") == 1


def test_prompts_receive_the_interview_context(fake_llm):
    fake = fake_llm()
    run(analyze_candidate_response_and_generate_new_question(*ARGS))
    joined = "\n".join(fake.prompts)
    for fragment in ("Tell me about yourself", "I am an engineer", "Backend role"):
        assert fragment in joined
    assert "Led a team" in joined


def test_feedback_and_question_calls_run_concurrently(fake_llm):
    """Both LLM calls must be in flight at the same time (a barrier proves it)."""
    barrier = threading.Barrier(2, timeout=5)

    def handler(prompt):
        barrier.wait()  # raises BrokenBarrierError if the calls were sequential
        if kind_of(prompt) == "question":
            return json.dumps({"next_question": "Q2"})
        return json.dumps({"feedback": "ok", "score": 5})

    fake_llm(handler)
    next_question, feedback = run(
        analyze_candidate_response_and_generate_new_question(*ARGS)
    )
    assert next_question == "Q2"
    assert feedback["score"] == 5.0


def test_timeout_raises_timeout_error(fake_llm):
    def slow(prompt):
        time.sleep(1.0)
        return json.dumps({"feedback": "ok", "score": 5, "next_question": "Q"})

    fake_llm(slow)
    started = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        run(analyze_candidate_response_and_generate_new_question(*ARGS, timeout=0.1))
    assert time.monotonic() - started < 0.9


def test_default_timeout_is_thirty_seconds():
    import inspect

    default = (
        inspect.signature(analyze_candidate_response_and_generate_new_question)
        .parameters["timeout"]
        .default
    )
    assert default == 30.0


def test_llm_exception_becomes_interview_analysis_error(fake_llm):
    def boom(prompt):
        raise RuntimeError("provider exploded")

    fake_llm(boom)
    with pytest.raises(InterviewAnalysisError, match="provider exploded"):
        run(analyze_candidate_response_and_generate_new_question(*ARGS))
    with pytest.raises(InterviewAnalysisError, match="provider exploded"):
        run(get_feedback_of_candidate_response(*ARGS))
    with pytest.raises(InterviewAnalysisError, match="provider exploded"):
        run(get_next_question(ARGS[0], ARGS[1], ARGS[3], ARGS[2]))


def test_unparseable_reply_is_retried_once_then_fails(fake_llm):
    fake = fake_llm(lambda prompt: "I cannot answer in JSON")
    with pytest.raises(InterviewAnalysisError):
        run(get_feedback_of_candidate_response(*ARGS))
    assert len(fake.prompts) == 2


def test_unparseable_reply_succeeds_on_the_retry(fake_llm):
    replies = iter(["oops", json.dumps({"feedback": "Fine", "score": 6})])
    fake = fake_llm(lambda prompt: next(replies))
    result = run(get_feedback_of_candidate_response(*ARGS))
    assert result == {"feedback": "Fine", "score": 6.0}
    assert len(fake.prompts) == 2


def test_missing_feedback_fields_raise(fake_llm):
    fake_llm(lambda prompt: json.dumps({"feedback": "no score"}))
    with pytest.raises(InterviewAnalysisError, match="score"):
        run(get_feedback_of_candidate_response(*ARGS))


def test_missing_next_question_raises(fake_llm):
    fake_llm(lambda prompt: json.dumps({"something_else": "x"}))
    with pytest.raises(InterviewAnalysisError, match="next_question"):
        run(get_next_question("q", "a", "highlights", "jd"))


@pytest.mark.parametrize(
    "raw, expected",
    [("8", 8.0), ("7/10", 7.0), (15, 10.0), (-2, 0.0), (6.5, 6.5)],
)
def test_feedback_score_is_coerced_and_clamped(fake_llm, raw, expected):
    fake_llm(lambda prompt: json.dumps({"feedback": "ok", "score": raw}))
    result = run(get_feedback_of_candidate_response(*ARGS))
    assert result["score"] == expected


def test_non_numeric_score_raises(fake_llm):
    fake_llm(lambda prompt: json.dumps({"feedback": "ok", "score": "excellent"}))
    with pytest.raises(InterviewAnalysisError, match="Invalid score"):
        run(get_feedback_of_candidate_response(*ARGS))


def test_error_in_one_task_fails_the_combined_call(fake_llm):
    def handler(prompt):
        if kind_of(prompt) == "question":
            return json.dumps({"nope": 1})
        return json.dumps({"feedback": "ok", "score": 5})

    fake_llm(handler)
    with pytest.raises(InterviewAnalysisError):
        run(analyze_candidate_response_and_generate_new_question(*ARGS))


def test_evaluate_answer_for_a_middle_question_asks_for_both(fake_llm):
    fake = fake_llm()
    feedback, next_question = run(evaluate_answer("Q1", "A1", "jd", "hl", False))
    assert next_question == "Generated question 1"
    assert feedback["score"] == 8.0
    assert (fake.count("feedback"), fake.count("question")) == (1, 1)


def test_evaluate_answer_for_the_last_question_asks_for_feedback_only(fake_llm):
    fake = fake_llm()
    feedback, next_question = run(evaluate_answer("Q5", "A5", "jd", "hl", True))
    assert next_question is None
    assert feedback["score"] == 8.0
    assert (fake.count("feedback"), fake.count("question")) == (1, 0)


def test_evaluate_answer_times_out_on_the_last_question_too(fake_llm):
    def slow(prompt):
        time.sleep(1.0)
        return json.dumps({"feedback": "ok", "score": 5})

    fake_llm(slow)
    with pytest.raises(asyncio.TimeoutError):
        run(evaluate_answer("Q", "A", "jd", "hl", True, timeout=0.1))

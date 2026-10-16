import math
import re

MIN_SCORE = 0.0
MAX_SCORE = 10.0

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def coerce_score(value):
    """
    Convert an LLM score (number or string such as "8", "7.5" or "8/10") to a float
    clamped to the 0-10 range.

    Raises:
        ValueError: if the value cannot be interpreted as a finite number.
    """
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Invalid score: {value!r}")

    if isinstance(value, str):
        match = _NUMBER_RE.search(value.replace(",", "."))
        if not match:
            raise ValueError(f"Invalid score: {value!r}")
        number = float(match.group())
    else:
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid score: {value!r}") from error

    if not math.isfinite(number):
        raise ValueError(f"Invalid score: {value!r}")

    return max(MIN_SCORE, min(MAX_SCORE, number))


def get_overall_evaluation_score(conversations):
    """
    Average of the per-question scores (0-10).

    Conversations whose "Evaluation" is missing or not a valid number are skipped.
    Returns 0.0 when there is nothing to average.
    """
    scores = []
    for conversation in conversations or []:
        try:
            scores.append(coerce_score(conversation.get("Evaluation")))
        except (ValueError, AttributeError):
            continue

    if not scores:
        return 0.0
    return sum(scores) / len(scores)

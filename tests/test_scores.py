import math

import pytest

from utils.evaluation import coerce_score, get_overall_evaluation_score


@pytest.mark.parametrize(
    "value, expected",
    [
        (8, 8.0),
        (7.5, 7.5),
        ("8", 8.0),
        ("7.5", 7.5),
        (" 9 ", 9.0),
        ("8/10", 8.0),
        ("Score: 6 out of 10", 6.0),
        ("7,5", 7.5),
        (0, 0.0),
        (10, 10.0),
        (15, 10.0),
        ("12", 10.0),
        (-3, 0.0),
        ("-2", 0.0),
        (99.9, 10.0),
    ],
)
def test_coerce_and_clamp(value, expected):
    result = coerce_score(value)
    assert isinstance(result, float)
    assert result == expected


@pytest.mark.parametrize(
    "value", [None, "", "great", True, False, [], {}, float("nan"), math.inf, "inf"]
)
def test_invalid_scores_raise_value_error(value):
    with pytest.raises(ValueError):
        coerce_score(value)


def test_overall_score_is_the_average():
    conversations = [{"Evaluation": 8}, {"Evaluation": 6}, {"Evaluation": 7}]
    assert get_overall_evaluation_score(conversations) == 7.0


def test_overall_score_handles_strings_and_out_of_range():
    conversations = [{"Evaluation": "8"}, {"Evaluation": 25}, {"Evaluation": -4}]
    assert get_overall_evaluation_score(conversations) == pytest.approx(6.0)


def test_overall_score_skips_missing_and_invalid_values():
    conversations = [
        {"Evaluation": 8},
        {},
        {"Evaluation": None},
        {"Evaluation": "n/a"},
        {"Evaluation": 6},
    ]
    assert get_overall_evaluation_score(conversations) == 7.0


@pytest.mark.parametrize(
    "conversations", [[], None, [{}], [{"Evaluation": "x"}], [None]]
)
def test_overall_score_is_zero_when_nothing_is_usable(conversations):
    assert get_overall_evaluation_score(conversations) == 0.0

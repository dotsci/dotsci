import math

from dotsci_runner.compare import compare_targets, within_tolerance


def test_absolute_within():
    assert within_tolerance(0.41, 0.42, {"type": "absolute", "value": 0.02})


def test_absolute_boundary_is_inclusive():
    assert within_tolerance(1.0, 1.5, {"type": "absolute", "value": 0.5})


def test_absolute_outside():
    assert not within_tolerance(0.41, 0.50, {"type": "absolute", "value": 0.02})


def test_relative_within():
    assert within_tolerance(100.0, 104.0, {"type": "relative", "value": 0.05})


def test_relative_outside():
    assert not within_tolerance(100.0, 110.0, {"type": "relative", "value": 0.05})


def test_relative_uses_magnitude_of_published():
    assert within_tolerance(-100.0, -104.0, {"type": "relative", "value": 0.05})


def test_zero_tolerance_requires_exact_match():
    assert within_tolerance(1200, 1200, {"type": "absolute", "value": 0})
    assert not within_tolerance(1200, 1201, {"type": "absolute", "value": 0})


def test_non_finite_never_matches():
    tol = {"type": "absolute", "value": 1e9}
    assert not within_tolerance(1.0, float("nan"), tol)
    assert not within_tolerance(1.0, float("inf"), tol)


def _targets():
    return [
        {"name": "a", "published": 0.41, "tolerance": {"type": "absolute", "value": 0.02}},
        {"name": "b", "published": 1200, "tolerance": {"type": "absolute", "value": 0}},
    ]


def test_all_match_is_reproduced():
    comparisons, outcome = compare_targets(_targets(), {"a": 0.42, "b": 1200})
    assert outcome == "reproduced"
    assert all(c["match"] for c in comparisons)


def test_one_miss_is_not_reproduced():
    comparisons, outcome = compare_targets(_targets(), {"a": 0.42, "b": 1190})
    assert outcome == "not_reproduced"
    assert [c["match"] for c in comparisons] == [True, False]


def test_missing_result_cannot_reproduce():
    comparisons, outcome = compare_targets(_targets(), {"a": 0.41})
    assert outcome == "not_reproduced"
    assert comparisons[1]["match"] is False
    assert math.isnan(comparisons[1]["rerun"])


def test_difference_is_rerun_minus_published():
    comparisons, _ = compare_targets(_targets(), {"a": 0.40, "b": 1200})
    assert math.isclose(comparisons[0]["difference"], -0.01)

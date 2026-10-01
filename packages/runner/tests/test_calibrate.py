import copy
import json
from pathlib import Path

import pytest

from dotsci_runner.calibrate import (
    STABLE_MATCH,
    STABLE_MISS,
    UNSTABLE,
    CalibrationError,
    calibrate,
    render,
)
from dotsci_runner.cli import main
from dotsci_runner.compare import compare_targets
from dotsci_runner.manifest import load_manifest
from dotsci_runner.record import build_run_record

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = load_manifest(ROOT / "examples" / "demo-claim" / "manifest.json")
INPUT = {"measurements.csv": "a" * 64}
OUTPUT = {"results.json": "b" * 64}


def record(mean_difference, *, sample_size=200, job="job-1"):
    values = {"mean_difference": mean_difference, "sample_size": sample_size}
    comparisons, outcome = compare_targets(MANIFEST["targets"], values)
    return build_run_record(
        MANIFEST, comparisons, outcome, job_id=job, role="runner",
        input_hashes=dict(INPUT), output_hashes=dict(OUTPUT),
    )


def runs(*values):
    return [record(v, job=f"job-{i}") for i, v in enumerate(values)]


def target(result, name="mean_difference"):
    return next(t for t in result.targets if t.name == name)


def test_tight_reruns_are_stable_match():
    result = calibrate(runs(0.63, 0.631, 0.629, 0.632, 0.628), margin=1)
    t = target(result)
    assert t.verdict == STABLE_MATCH and t.matches == 5 and not result.spec_issue


def test_statistics_are_computed():
    t = target(calibrate(runs(0.62, 0.64), margin=1))
    assert t.n == 2
    assert t.mean == pytest.approx(0.63)
    assert t.minimum == 0.62 and t.maximum == 0.64
    assert t.spread == pytest.approx(0.02)
    assert t.stdev == pytest.approx(0.0141421356, rel=1e-6)


def test_suggested_absolute_is_largest_deviation_times_margin():
    published = target(calibrate(runs(0.63, 0.63), margin=1)).published
    result = calibrate(runs(published + 0.01, published - 0.03), margin=2)
    t = target(result)
    assert t.max_deviation == pytest.approx(0.03)
    assert t.suggested_absolute == pytest.approx(0.06)
    assert t.suggested_relative == pytest.approx(0.06 / abs(published))


def test_suggested_tolerance_would_match_every_rerun_at_margin_one():
    from dotsci_runner.compare import within_tolerance

    values = [0.60, 0.66, 0.63, 0.7]
    t = target(calibrate(runs(*values), margin=1))
    tol = {"type": "absolute", "value": t.suggested_absolute}
    assert all(within_tolerance(t.published, v, tol) for v in values)
    tighter = {"type": "absolute", "value": t.suggested_absolute * 0.999}
    assert not all(within_tolerance(t.published, v, tighter) for v in values)


def test_mixed_matches_are_a_spec_issue():
    t_info = target(calibrate(runs(0.63, 0.63), margin=1))
    tol = t_info.tolerance["value"]
    result = calibrate(runs(t_info.published, t_info.published + tol * 3), margin=1)
    assert target(result).verdict == UNSTABLE and result.spec_issue


def test_agreeing_miss_is_not_noise():
    result = calibrate(runs(5.0, 5.001, 4.999), margin=1)
    assert target(result).verdict == STABLE_MISS and not result.spec_issue
    assert "tuning" in render(result)


def test_few_reruns_warn_and_many_do_not():
    assert any("lower bounds" in w for w in calibrate(runs(0.63, 0.63), margin=1).warnings)
    many = calibrate(runs(0.63, 0.631, 0.629, 0.632, 0.628), margin=1)
    assert not any("lower bounds" in w for w in many.warnings)


def test_identical_reruns_are_flagged_deterministic():
    result = calibrate(runs(0.63, 0.63, 0.63, 0.63, 0.63), margin=1)
    assert any("deterministic" in w for w in result.warnings)
    assert target(result).stdev == 0


def test_zero_published_has_no_relative_suggestion():
    records = runs(0.63, 0.63)
    for r in records:
        for c in r["comparisons"]:
            if c["name"] == "mean_difference":
                c["published"] = 0.0
    assert target(calibrate(records, margin=1)).suggested_relative is None


@pytest.mark.parametrize("margin", [0.99, 0, -1, float("nan"), float("inf")])
def test_bad_margin_is_rejected(margin):
    with pytest.raises(CalibrationError):
        calibrate(runs(0.63, 0.63), margin=margin)


def test_needs_two_runs():
    with pytest.raises(CalibrationError):
        calibrate(runs(0.63), margin=1)


def test_different_inputs_are_not_calibrated_together():
    a, b = runs(0.63, 0.63)
    b["input_hashes"]["measurements.csv"] = "c" * 64
    with pytest.raises(CalibrationError, match="not comparable"):
        calibrate([a, b], margin=1)


def test_different_seed_is_not_calibrated_together():
    a, b = runs(0.63, 0.63)
    b["environment"]["seed"] = (a["environment"].get("seed") or 0) + 1
    with pytest.raises(CalibrationError, match="not comparable"):
        calibrate([a, b], margin=1)


def test_invalid_record_is_rejected():
    a, b = runs(0.63, 0.63)
    del b["claim_id"]
    with pytest.raises(CalibrationError, match="valid run record"):
        calibrate([a, b], margin=1)


def test_non_finite_rerun_is_rejected():
    a, b = runs(0.63, 0.63)
    b["comparisons"][0]["rerun"] = float("nan")
    with pytest.raises(CalibrationError, match="non-finite"):
        calibrate([a, b], margin=1)


def test_inputs_are_not_mutated():
    records = runs(0.63, 0.64, 0.62)
    snapshot = copy.deepcopy(records)
    calibrate(records, margin=2)
    assert records == snapshot


def write(tmp_path, records):
    paths = []
    for i, r in enumerate(records):
        p = tmp_path / f"run{i}.json"
        p.write_text(json.dumps(r))
        paths.append(str(p))
    return paths


def test_cli_ok_and_json(tmp_path, capsys):
    paths = write(tmp_path, runs(0.63, 0.631, 0.629))
    assert main(["calibrate", *paths, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["runs"] == 3 and data["spec_issue"] is False


def test_cli_exit_one_on_spec_issue(tmp_path, capsys):
    info = target(calibrate(runs(0.63, 0.63), margin=1))
    paths = write(tmp_path, runs(info.published, info.published + info.tolerance["value"] * 3))
    assert main(["calibrate", *paths]) == 1
    assert "spec_issue: yes" in capsys.readouterr().out


def test_cli_reports_unreadable_file(tmp_path, capsys):
    assert main(["calibrate", str(tmp_path / "missing.json"), str(tmp_path / "x.json")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_cli_reports_calibration_error(tmp_path, capsys):
    paths = write(tmp_path, runs(0.63, 0.63))
    assert main(["calibrate", *paths, "--margin", "0.5"]) == 1
    assert "margin" in capsys.readouterr().err


def test_bias_is_mean_minus_published():
    published = target(calibrate(runs(0.63, 0.63), margin=1)).published
    assert target(calibrate(runs(published + 0.02, published + 0.04), margin=1)).bias == pytest.approx(0.03)
    assert target(calibrate(runs(published - 0.02, published - 0.04), margin=1)).bias == pytest.approx(-0.03)

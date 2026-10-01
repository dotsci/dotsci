import copy
import json
from pathlib import Path

from dotsci_runner.cli import main
from dotsci_runner.compare import compare_targets
from dotsci_runner.dispute import (
    AGREE,
    DISAGREE,
    NOT_COMPARABLE,
    diff_runs,
    render,
    validate_run_record,
)
from dotsci_runner.manifest import load_manifest
from dotsci_runner.record import build_run_record

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = load_manifest(ROOT / "examples" / "demo-claim" / "manifest.json")
INPUT = {"measurements.csv": "a" * 64}
OUTPUT = {"results.json": "b" * 64}


def record(values, *, role="runner", job="job-1", inputs=None, outputs=None):
    comparisons, outcome = compare_targets(MANIFEST["targets"], values)
    return build_run_record(
        MANIFEST, comparisons, outcome, job_id=job, role=role,
        input_hashes=dict(inputs if inputs is not None else INPUT),
        output_hashes=dict(outputs if outputs is not None else OUTPUT),
    )


GOOD = {"mean_difference": 0.63, "sample_size": 200}


def test_identical_runs_agree():
    evidence = diff_runs(record(GOOD), record(GOOD, role="challenger", job="job-2"))
    assert evidence.verdict == AGREE and evidence.reasons == ()


def test_small_numeric_difference_inside_tolerance_still_agrees_and_is_reported():
    evidence = diff_runs(record(GOOD), record({"mean_difference": 0.64, "sample_size": 200}))
    assert evidence.verdict == AGREE
    c = next(c for c in evidence.comparisons if c.name == "mean_difference")
    assert c.status == "agree" and abs(c.value_difference - 0.01) < 1e-9


def test_disagreement_names_the_comparison_and_the_size_of_the_difference():
    runner = record(GOOD)
    challenger = record({"mean_difference": 0.90, "sample_size": 200}, role="challenger")
    evidence = diff_runs(runner, challenger)
    assert evidence.verdict == DISAGREE
    assert evidence.outcome_a == "reproduced" and evidence.outcome_b == "not_reproduced"
    text = " ".join(evidence.reasons)
    assert "mean_difference" in text and "a=0.63" in text and "b=0.9" in text and "0.27" in text
    assert "sample_size" not in text


def test_a_target_reported_by_only_one_side_is_a_disagreement():
    runner = record(GOOD)
    challenger = copy.deepcopy(runner)
    challenger["comparisons"] = [c for c in challenger["comparisons"] if c["name"] != "sample_size"]
    evidence = diff_runs(runner, challenger)
    assert evidence.verdict == DISAGREE
    assert any("sample_size" in r and "only reported by a" in r for r in evidence.reasons)


def test_different_input_hashes_make_the_runs_not_comparable():
    evidence = diff_runs(record(GOOD), record(GOOD, inputs={"measurements.csv": "c" * 64}))
    assert evidence.verdict == NOT_COMPARABLE
    assert evidence.inputs[0].status == "different"
    assert any("measurements.csv" in r for r in evidence.reasons)


def test_a_missing_input_makes_the_runs_not_comparable():
    evidence = diff_runs(record(GOOD), record(GOOD, inputs={}))
    assert evidence.verdict == NOT_COMPARABLE
    assert evidence.inputs[0].status == "only_a"


def test_different_environment_makes_the_runs_not_comparable():
    a, b = record(GOOD), record(GOOD)
    b["environment"] = {"image_digest": "sha256:" + "1" * 64, "seed": a["environment"].get("seed")}
    assert diff_runs(a, b).verdict == NOT_COMPARABLE
    c = record(GOOD)
    c["environment"] = dict(c["environment"], seed=999)
    assert diff_runs(a, c).verdict == NOT_COMPARABLE


def test_different_claims_are_not_comparable():
    a, b = record(GOOD), record(GOOD)
    b["claim_id"] = "another-claim"
    evidence = diff_runs(a, b)
    assert evidence.verdict == NOT_COMPARABLE and evidence.claim_id is None


def test_output_hash_differences_are_informational_only():
    evidence = diff_runs(record(GOOD), record(GOOD, outputs={"results.json": "d" * 64, "plot.png": "e" * 64}))
    assert evidence.verdict == AGREE
    assert {o.name for o in evidence.outputs} == {"results.json", "plot.png"}


def test_a_spec_issue_against_a_clean_run_is_a_disagreement():
    runner = record(GOOD)
    challenger = copy.deepcopy(runner)
    challenger["outcome"] = "spec_issue"
    evidence = diff_runs(runner, challenger)
    assert evidence.verdict == DISAGREE and any("outcomes differ" in r for r in evidence.reasons)


def test_swapping_the_runs_gives_the_same_verdict():
    a = record(GOOD)
    b = record({"mean_difference": 0.9, "sample_size": 200})
    assert diff_runs(a, b).verdict == diff_runs(b, a).verdict


def test_validation_and_rendering():
    assert validate_run_record(record(GOOD)) == []
    assert validate_run_record({"nope": 1})
    assert validate_run_record([])
    text = render(diff_runs(record(GOOD), record({"mean_difference": 0.9, "sample_size": 200})))
    assert "verdict: disagree" in text and "mean_difference" in text


def write(tmp_path, name, rec):
    path = tmp_path / name
    path.write_text(json.dumps(rec))
    return str(path)


def test_diff_command_exit_codes(tmp_path, capsys):
    a = write(tmp_path, "a.json", record(GOOD))
    same = write(tmp_path, "same.json", record(GOOD, role="challenger"))
    other = write(tmp_path, "other.json", record({"mean_difference": 0.9, "sample_size": 200}))
    assert main(["diff", a, same]) == 0
    capsys.readouterr()
    assert main(["diff", a, other]) == 1
    assert "mean_difference" in capsys.readouterr().out
    assert main(["diff", a, other, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == DISAGREE


def test_diff_command_rejects_unreadable_or_invalid_records(tmp_path, capsys):
    a = write(tmp_path, "a.json", record(GOOD))
    bad = write(tmp_path, "bad.json", {"not": "a run"})
    assert main(["diff", a, str(tmp_path / "missing.json")]) == 1
    assert main(["diff", a, bad]) == 1
    assert "not a valid run record" in capsys.readouterr().err

"""Replay the shared conformance vectors against the reference implementation."""

import json
from pathlib import Path

import pytest

from dotsci_protocol import assignment, commit, settlement

VECTORS = Path(__file__).resolve().parents[3] / "spec" / "vectors"


def load(name):
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


MERKLE = load("merkle.json")
ASSIGN = load("assignment.json")
SETTLE = load("settlement.json")


def test_merkle_trees():
    for t in MERKLE["trees"]:
        leaves = [bytes.fromhex(x) for x in t["leaves"]]
        assert commit.merkle_root(leaves).hex() == t["root"], t["name"]
        for i, expected in enumerate(t["audit_paths"]):
            assert [s.hex() for s in commit.audit_path(leaves, i)] == expected, (t["name"], i)
            assert commit.verify_inclusion(
                bytes.fromhex(t["root"]), len(leaves), i, leaves[i], [bytes.fromhex(x) for x in expected]
            ), (t["name"], i)


def test_inclusion_verdicts():
    for c in MERKLE["inclusion"]:
        got = commit.verify_inclusion(
            bytes.fromhex(c["root"]), c["size"], c["index"], bytes.fromhex(c["leaf"]),
            [bytes.fromhex(x) for x in c["siblings"]],
        )
        assert got is c["valid"], c["name"]


def test_file_commitments():
    for f in MERKLE["files"]:
        c = commit.commit_files(f["input"])
        assert [p for p, _ in c.files] == f["order"], f["name"]
        assert [commit._file_leaf(p, d).hex() for p, d in c.files] == f["leaves"], f["name"]
        assert c.root == f["root"] and c.size == f["size"], f["name"]
        for proof in f["proofs"]:
            built = c.prove(proof["path"])
            assert built.index == proof["index"] and list(built.siblings) == proof["siblings"], (f["name"], proof["path"])
            assert built.verify(f["root"])


def test_streams():
    for s in ASSIGN["streams"]:
        stream = assignment.Stream(bytes.fromhex(s["seed"]), s["claim_id"], s["role"])
        assert [str(stream.next_word()) for _ in s["words"]] == s["words"]


def test_uniform_below():
    for u in ASSIGN["uniform_below"]:
        it = iter(int(w) for w in u["words"])
        assert str(assignment.uniform_below(lambda: next(it), int(u["n"]))) == u["result"]


def test_draws():
    for d in ASSIGN["draws"]:
        got = assignment.draw(bytes.fromhex(d["seed"]), d["claim_id"], d["role"], d["candidates"], d["count"])
        assert got == d["picks"]
        assert assignment.verify_draw(bytes.fromhex(d["seed"]), d["claim_id"], d["role"], d["candidates"], d["picks"])


def test_assignment_errors():
    for e in ASSIGN["errors"]:
        with pytest.raises(assignment.AssignmentError):
            assignment.draw(bytes.fromhex(e["seed"]), e["claim_id"], e["role"], e["candidates"], e["count"])


def _case(data):
    return settlement.Case(
        kind=data["kind"], bounty=int(data["bounty"]), runner=data["runner"], runner_stake=int(data["runner_stake"]),
        challenger=data["challenger"], challenger_stake=int(data["challenger_stake"]),
        reviewer_stakes={k: int(v) for k, v in data["reviewer_stakes"].items()}, votes=dict(data["votes"]),
    )


def test_settlement_vectors():
    assert len(SETTLE["cases"]) > 100
    for c in SETTLE["cases"]:
        params = settlement.Params(**SETTLE["params"][c["params"]])
        case = _case(c["case"])
        if c.get("error") == "tie":
            with pytest.raises(settlement.TieError):
                settlement.settle(case, params)
        elif c.get("error") == "invalid":
            with pytest.raises(settlement.SettlementError):
                settlement.settle(case, params)
        else:
            got = settlement.settle(case, params)
            e = c["expected"]
            assert got.verdict == e["verdict"], c["name"]
            assert {k: str(v) for k, v in sorted(got.payouts.items())} == e["payouts"], c["name"]
            assert str(got.to_vault) == e["to_vault"] and str(got.to_treasury) == e["to_treasury"], c["name"]


def test_every_settlement_vector_conserves_value():
    for c in SETTLE["cases"]:
        if "expected" not in c:
            continue
        data = c["case"]
        total_in = int(data["bounty"]) + int(data["runner_stake"]) + int(data["challenger_stake"]) + sum(
            int(v) for v in data["reviewer_stakes"].values()
        )
        e = c["expected"]
        assert sum(int(v) for v in e["payouts"].values()) + int(e["to_vault"]) + int(e["to_treasury"]) == total_in, c["name"]


def test_vectors_cover_every_case_kind_and_outcome():
    kinds = {c["case"]["kind"] for c in SETTLE["cases"] if "expected" in c}
    assert kinds == {"unchallenged", "confirmed", "disputed", "spec_issue"}
    verdicts = {c["expected"]["verdict"] for c in SETTLE["cases"] if "expected" in c}
    assert verdicts == {"runner", "challenger", "none"}
    assert any(c["expected"]["to_treasury"] != "0" for c in SETTLE["cases"] if "expected" in c)
    assert any(len(c["expected"]["payouts"]) and max(len(v) for v in c["expected"]["payouts"].values()) > 30
               for c in SETTLE["cases"] if "expected" in c)

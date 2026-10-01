#!/usr/bin/env python3
"""Generate the language neutral conformance vectors in spec/vectors.

The vectors pin down the byte level behavior of the parts of DotSci that other
implementations (a Solidity contract, a TypeScript client) must reproduce exactly:
manifest hashing, run commitments, assignment, and settlement.

They are produced by the reference code and checked two ways: the reference tests
replay them, and spec/vectors/verify.py replays them with an independent
implementation that uses only the standard library. If the two ever disagree, one of
them is wrong, and that is the point.

Usage:
    python tools/gen_vectors.py           write spec/vectors/*.json
    python tools/gen_vectors.py --check   fail if the files on disk are out of date
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "runner" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "protocol" / "src"))

from dotsci_protocol import assignment, commit, settlement  # noqa: E402
from dotsci_runner.manifest import canonical_json, manifest_hash  # noqa: E402

OUT = ROOT / "spec" / "vectors"
VERSION = 1

# Numbers that can exceed 2**53 are written as decimal strings, so a JSON parser in
# any language reads them exactly.


def _s(n: int) -> str:
    return str(n)


class Rng:
    """Deterministic generator for building cases. Not part of the protocol."""

    def __init__(self, label: str) -> None:
        self._stream = assignment.Stream(hashlib.sha256(label.encode()).digest(), "vectors", "gen")

    def below(self, n: int) -> int:
        return assignment.uniform_below(self._stream.next_word, n)

    def between(self, lo: int, hi: int) -> int:
        return lo + self.below(hi - lo + 1)

    def choice(self, items):
        return items[self.below(len(items))]


# ---- manifest hash ----------------------------------------------------------


def manifest_vectors() -> dict:
    demo = json.loads((ROOT / "examples" / "demo-claim" / "manifest.json").read_text(encoding="utf-8"))
    objects = {
        "empty_object": {},
        "key_order_ignored": {"b": 1, "a": {"d": [3, 2, 1], "c": None}},
        "key_order_ignored_reversed": {"a": {"c": None, "d": [3, 2, 1]}, "b": 1},
        "unicode_is_not_escaped": {"name": "Zürich ångström 研究"},
        "string_escapes": {"s": 'quote " backslash \\ newline \n tab \t'},
        "integers": {"zero": 0, "negative": -7, "large": 9007199254740993},
        "floats_use_shortest_repr": {"a": 0.1, "b": 1e-07, "c": 1e22, "d": 5.0, "e": 0.63},
        "nested_arrays": {"x": [[1, 2], [], [{"k": "v"}]]},
        "booleans_and_null": {"t": True, "f": False, "n": None},
        "demo_claim_manifest": demo,
    }
    cases = []
    for name, obj in objects.items():
        cases.append(
            {
                "name": name,
                "manifest": obj,
                "canonical": canonical_json(obj).decode("utf-8"),
                "sha256": manifest_hash(obj),
            }
        )
    return {
        "version": VERSION,
        "description": "Canonical JSON and SHA-256 of a manifest. canonical is the exact UTF-8 text that is hashed.",
        "rules": [
            "keys sorted by Unicode code point, recursively",
            "separators are ',' and ':' with no whitespace",
            "text is UTF-8 and non-ASCII characters are not escaped",
            "NaN and infinity are rejected",
            "numbers follow the shortest round-trip form of Python's json module, so 5.0 stays 5.0 and 1e-07 stays 1e-07",
        ],
        "cases": cases,
    }


# ---- merkle -----------------------------------------------------------------

RFC_LEAVES = [
    "", "00", "10", "2021", "3031", "40414243", "5051525354555657", "606162636465666768696a6b6c6d6e6f",
]


def merkle_vectors() -> dict:
    rng = Rng("merkle")
    trees = []
    sets = {"rfc6962_first_8": [bytes.fromhex(x) for x in RFC_LEAVES]}
    for n in (0, 1, 2, 3, 5, 6, 7, 9, 15, 16, 17, 33):
        sets[f"generated_{n}"] = [bytes(rng.below(256) for _ in range(rng.between(0, 40))) for _ in range(n)]
    for name, leaves in sets.items():
        for n in (range(len(leaves) + 1) if name == "rfc6962_first_8" else [len(leaves)]):
            part = leaves[:n]
            paths = [[s.hex() for s in commit.audit_path(part, i)] for i in range(n)]
            trees.append(
                {
                    "name": f"{name}" if name != "rfc6962_first_8" else f"rfc6962_first_{n}",
                    "leaves": [x.hex() for x in part],
                    "root": commit.merkle_root(part).hex(),
                    "audit_paths": paths,
                }
            )

    base = [bytes.fromhex(x) for x in RFC_LEAVES]
    root = commit.merkle_root(base)
    good = [s for s in commit.audit_path(base, 5)]
    bad = []

    def add(name, **kw):
        case = {"name": name, "root": root.hex(), "size": 8, "index": 5, "leaf": base[5].hex(),
                "siblings": [s.hex() for s in good], "valid": False}
        case.update(kw)
        bad.append(case)

    add("valid", valid=True)
    add("wrong_leaf", leaf="deadbeef")
    add("wrong_index", index=4)
    add("index_out_of_range", index=8)
    add("size_too_small_for_path", size=4)
    add("path_too_long", siblings=[s.hex() for s in good] + ["00" * 32])
    add("path_too_short", siblings=[s.hex() for s in good][:-1])
    flipped = bytearray(good[0])
    flipped[0] ^= 1
    add("flipped_sibling_bit", siblings=[flipped.hex()] + [s.hex() for s in good[1:]])
    add("swapped_siblings", siblings=[good[1].hex(), good[0].hex(), good[2].hex()])
    add("wrong_root", root="11" * 32)
    # Second preimage attempt: present the two child hashes of the root as the data of a
    # one leaf tree. The 0x00 and 0x01 prefixes make this fail.
    pair = [b"left", b"right"]
    pair_root = commit.merkle_root(pair)
    add("interior_node_as_leaf", root=pair_root.hex(), size=1, index=0, siblings=[],
        leaf=(commit.leaf_hash(pair[0]) + commit.leaf_hash(pair[1])).hex())

    files = []
    file_sets = {
        "three_files": {
            "src/main.py": hashlib.sha256(b"print('hi')").hexdigest(),
            "data/in.csv": hashlib.sha256(b"a,b\n1,2\n").hexdigest(),
            "README.md": hashlib.sha256(b"").hexdigest(),
        },
        "path_order_is_by_bytes": {
            "b": "01" * 32, "a": "02" * 32, "a/b": "03" * 32, "B": "04" * 32, "é": "05" * 32, "z": "06" * 32,
        },
        "single_file": {"results.json": "ab" * 32},
        "empty": {},
        "uppercase_digest_is_normalized": {"x": "AB" * 32},
    }
    for name, mapping in file_sets.items():
        c = commit.commit_files(mapping)
        files.append(
            {
                "name": name,
                "input": mapping,
                "order": [p for p, _ in c.files],
                "leaves": [commit._file_leaf(p, d).hex() for p, d in c.files],
                "root": c.root,
                "size": c.size,
                "proofs": [
                    {"path": p, "index": pr.index, "siblings": list(pr.siblings)}
                    for p in (p for p, _ in c.files)
                    for pr in [c.prove(p)]
                ],
            }
        )

    return {
        "version": VERSION,
        "description": "RFC 6962 Merkle trees over SHA-256 and the DotSci file leaf format.",
        "leaf_prefix": "00",
        "node_prefix": "01",
        "file_leaf": "uint32_be(len(path)) || path (UTF-8) || sha256(file), leaves ordered by path bytes",
        "trees": trees,
        "inclusion": bad,
        "files": files,
    }


# ---- assignment -------------------------------------------------------------


def assignment_vectors() -> dict:
    rng = Rng("assignment")
    streams = []
    for i, (claim, role) in enumerate([("claim-1", "runner"), ("claim-1", "reviewer"), ("claim-2", "runner"), ("", "")]):
        seed = hashlib.sha256(f"seed-{i}".encode()).digest()
        s = assignment.Stream(seed, claim, role)
        streams.append({"seed": seed.hex(), "claim_id": claim, "role": role, "words": [_s(s.next_word()) for _ in range(10)]})
    long_seed = bytes(range(16))
    s = assignment.Stream(long_seed, "claim-1", "runner")
    streams.append({"seed": long_seed.hex(), "claim_id": "claim-1", "role": "runner", "words": [_s(s.next_word()) for _ in range(10)]})

    top = (1 << 64) - 1
    uniform = []
    for n, words in [
        (1, [5]), (2, [top]), (3, [top, top - 1]), (3, [top, top, 7]), (10, [top, top - 5, top - 6]),
        ((1 << 63) + 1, [top, (1 << 63)]), (7, [0]), (7, [41]),
    ]:
        it = iter(words)
        uniform.append({"n": _s(n), "words": [_s(w) for w in words], "result": _s(assignment.uniform_below(lambda: next(it), n))})

    draws = []
    for i in range(14):
        seed = hashlib.sha256(f"draw-{i}".encode()).digest()
        size = rng.between(1, 12)
        pool = [f"agent-{rng.below(30)}" for _ in range(size + rng.below(4))]
        distinct = len(set(pool))
        count = rng.between(0, distinct)
        claim = f"claim-{rng.below(5)}"
        role = rng.choice(["runner", "reviewer"])
        draws.append(
            {
                "seed": seed.hex(), "claim_id": claim, "role": role, "candidates": pool, "count": count,
                "picks": assignment.draw(seed, claim, role, pool, count),
            }
        )
    errors = [
        {"name": "seed_too_short", "seed": "00" * 15, "claim_id": "c", "role": "runner", "candidates": ["a"], "count": 1},
        {"name": "count_exceeds_pool", "seed": "00" * 16, "claim_id": "c", "role": "runner", "candidates": ["a", "a", "b"], "count": 3},
    ]
    for e in errors:
        try:
            assignment.draw(bytes.fromhex(e["seed"]), e["claim_id"], e["role"], e["candidates"], e["count"])
        except assignment.AssignmentError:
            e["error"] = True
        else:  # pragma: no cover
            raise SystemExit(f"error vector {e['name']} did not fail")
    return {
        "version": VERSION,
        "description": "Deterministic assignment. Words are decimal strings (unsigned 64 bit).",
        "domain": assignment.DOMAIN.decode(),
        "stream": "word k is the big endian first 8 bytes of SHA-256(domain || lp(seed) || lp(claim) || lp(role) || uint64_be(block)), 4 words per block, lp = uint32_be length prefix",
        "draw": "sort and de-duplicate candidates, then partial Fisher-Yates: for i in 0..count, j = i + uniform_below(len - i), swap, pick pool[i]",
        "streams": streams,
        "uniform_below": uniform,
        "draws": draws,
        "errors": errors,
    }


# ---- settlement -------------------------------------------------------------

PARAM_SETS = {
    # Test values only. The real parameters are open decisions (see docs/mechanism.md).
    "mid": dict(runner_slash_bps=5000, challenger_slash_bps=3000, reviewer_slash_bps=2000, reviewer_pool_bps=4000,
                challenger_reward_bps=2500, confirm_reward_bps=500, spec_issue_pay_bps=1000),
    "zero": dict(runner_slash_bps=0, challenger_slash_bps=0, reviewer_slash_bps=0, reviewer_pool_bps=0,
                 challenger_reward_bps=0, confirm_reward_bps=0, spec_issue_pay_bps=0),
    "full": dict(runner_slash_bps=10000, challenger_slash_bps=10000, reviewer_slash_bps=10000, reviewer_pool_bps=10000,
                 challenger_reward_bps=10000, confirm_reward_bps=10000, spec_issue_pay_bps=10000),
    "odd": dict(runner_slash_bps=3333, challenger_slash_bps=777, reviewer_slash_bps=1234, reviewer_pool_bps=6667,
                challenger_reward_bps=4321, confirm_reward_bps=99, spec_issue_pay_bps=9999),
}


def _case_json(case: settlement.Case) -> dict:
    return {
        "kind": case.kind, "bounty": _s(case.bounty), "runner": case.runner, "runner_stake": _s(case.runner_stake),
        "challenger": case.challenger, "challenger_stake": _s(case.challenger_stake),
        "reviewer_stakes": {k: _s(v) for k, v in (case.reviewer_stakes or {}).items()},
        "votes": dict(case.votes or {}),
    }


def _case_from_json(data: dict) -> settlement.Case:
    return settlement.Case(
        kind=data["kind"], bounty=int(data["bounty"]), runner=data["runner"], runner_stake=int(data["runner_stake"]),
        challenger=data["challenger"], challenger_stake=int(data["challenger_stake"]),
        reviewer_stakes={k: int(v) for k, v in data["reviewer_stakes"].items()}, votes=dict(data["votes"]),
    )


def settlement_vectors() -> dict:
    rng = Rng("settlement")
    raw: list[tuple[str, settlement.Case]] = []
    big = 10**60 + 12345
    raw += [
        ("unchallenged", settlement.Case("unchallenged", 1000, "r", 100)),
        ("spec_issue", settlement.Case("spec_issue", 1000, "r", 100)),
        ("spec_issue_dust", settlement.Case("spec_issue", 999, "r", 1)),
        ("confirmed", settlement.Case("confirmed", 1000, "r", 100, "c", 50)),
        ("disputed_runner_wins", settlement.Case(
            "disputed", 1000, "r", 100, "c", 50, {"a": 10, "b": 10, "d": 10}, {"a": "runner", "b": "runner", "d": "challenger"})),
        ("disputed_challenger_wins", settlement.Case(
            "disputed", 1000, "r", 100, "c", 50, {"a": 10, "b": 10, "d": 10}, {"a": "challenger", "b": "challenger", "d": "runner"})),
        ("disputed_tie_three_way_split_dust", settlement.Case(
            "disputed", 7, "r", 7, "c", 7, {"a": 7, "b": 7, "d": 7, "e": 7, "f": 7},
            {"a": "runner", "b": "runner", "d": "runner", "e": "challenger", "f": "challenger"})),
        ("huge_amounts", settlement.Case(
            "disputed", big, "r", big // 3, "c", big // 7, {"a": big // 11, "b": big // 13, "d": big // 17},
            {"a": "challenger", "b": "runner", "d": "challenger"})),
        ("zero_everything", settlement.Case("confirmed", 0, "r", 0, "c", 0)),
    ]
    for i in range(30):
        kind = rng.choice(["unchallenged", "spec_issue", "confirmed", "disputed", "disputed", "disputed"])
        amount = lambda: rng.choice([0, rng.between(0, 20), rng.between(0, 10**6), rng.between(0, 10**18)])  # noqa: E731
        challenger = kind in ("confirmed", "disputed")
        reviewers, votes = {}, {}
        if kind == "disputed":
            n = rng.choice([1, 3, 5, 7])
            for k in range(n):
                reviewers[f"rev{k}"] = amount()
                votes[f"rev{k}"] = rng.choice(["runner", "challenger"])
        raw.append((f"random_{i}", settlement.Case(
            kind, amount(), "r", amount(), "c" if challenger else None, amount() if challenger else 0, reviewers, votes)))

    cases = []
    for pname, params in PARAM_SETS.items():
        p = settlement.Params(**params)
        for name, case in raw:
            entry = {"name": f"{pname}/{name}", "params": pname, "case": _case_json(case)}
            try:
                result = settlement.settle(case, p)
            except settlement.TieError:
                entry["error"] = "tie"
            except settlement.SettlementError:
                entry["error"] = "invalid"
            else:
                entry["expected"] = {
                    "verdict": result.verdict,
                    "payouts": {k: _s(v) for k, v in sorted(result.payouts.items())},
                    "to_vault": _s(result.to_vault),
                    "to_treasury": _s(result.to_treasury),
                }
            cases.append(entry)

    invalid = [
        ("negative_amount", {"kind": "unchallenged", "bounty": "-1", "runner": "r", "runner_stake": "0",
                             "challenger": None, "challenger_stake": "0", "reviewer_stakes": {}, "votes": {}}, "invalid"),
        ("unknown_kind", {"kind": "mystery", "bounty": "1", "runner": "r", "runner_stake": "0",
                          "challenger": None, "challenger_stake": "0", "reviewer_stakes": {}, "votes": {}}, "invalid"),
        ("confirmed_without_challenger", {"kind": "confirmed", "bounty": "1", "runner": "r", "runner_stake": "0",
                                          "challenger": None, "challenger_stake": "0", "reviewer_stakes": {}, "votes": {}}, "invalid"),
        ("runner_is_also_reviewer", {"kind": "disputed", "bounty": "1", "runner": "r", "runner_stake": "1",
                                     "challenger": "c", "challenger_stake": "1", "reviewer_stakes": {"r": "1"},
                                     "votes": {"r": "runner"}}, "invalid"),
        ("missing_vote", {"kind": "disputed", "bounty": "1", "runner": "r", "runner_stake": "1",
                          "challenger": "c", "challenger_stake": "1", "reviewer_stakes": {"a": "1", "b": "1"},
                          "votes": {"a": "runner"}}, "invalid"),
        ("even_split", {"kind": "disputed", "bounty": "1", "runner": "r", "runner_stake": "1",
                        "challenger": "c", "challenger_stake": "1", "reviewer_stakes": {"a": "1", "b": "1"},
                        "votes": {"a": "runner", "b": "challenger"}}, "tie"),
    ]
    for name, data, expected in invalid:
        try:
            settlement.settle(_case_from_json(data), settlement.Params(**PARAM_SETS["mid"]))
        except settlement.TieError:
            got = "tie"
        except settlement.SettlementError:
            got = "invalid"
        else:  # pragma: no cover
            raise SystemExit(f"invalid vector {name} was accepted")
        assert got == expected, (name, got)
        cases.append({"name": f"invalid/{name}", "params": "mid", "case": data, "error": got})

    return {
        "version": VERSION,
        "description": "Settlement outcomes. Amounts are decimal strings, so uint256 values survive any JSON parser. Parameter sets are test values, not proposals.",
        "invariant": "sum(payouts) + to_vault + to_treasury == bounty + runner_stake + challenger_stake + sum(reviewer_stakes)",
        "params": PARAM_SETS,
        "cases": cases,
    }


GENERATORS = {
    "manifest-hash.json": manifest_vectors,
    "merkle.json": merkle_vectors,
    "assignment.json": assignment_vectors,
    "settlement.json": settlement_vectors,
}


def render(name: str) -> str:
    return json.dumps(GENERATORS[name](), indent=1, sort_keys=False, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = []
    for name in GENERATORS:
        text = render(name)
        path = OUT / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)} ({len(text)} bytes)")
    if stale:
        print("out of date: " + ", ".join(stale) + "\nrun: python tools/gen_vectors.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

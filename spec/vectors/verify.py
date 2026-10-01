#!/usr/bin/env python3
"""Independent check of the DotSci conformance vectors.

This file imports nothing from DotSci. It re-implements each rule from the descriptions
in README.md using only the Python standard library, then replays every vector. It is
also a compact reference for anyone porting the rules to another language.

    python spec/vectors/verify.py

Exit code 0 means every vector was reproduced.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sha = lambda b: hashlib.sha256(b).digest()  # noqa: E731


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


# ---- manifest hash ----------------------------------------------------------


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


# ---- merkle (RFC 6962) ------------------------------------------------------


def leaf_h(d: bytes) -> bytes:
    return sha(b"\x00" + d)


def node_h(a: bytes, b: bytes) -> bytes:
    return sha(b"\x01" + a + b)


def split(n: int) -> int:
    k = 1
    while k < n:
        k <<= 1
    return k >> 1


def mth(leaves):
    n = len(leaves)
    if n == 0:
        return sha(b"")
    if n == 1:
        return leaf_h(leaves[0])
    k = split(n)
    return node_h(mth(leaves[:k]), mth(leaves[k:]))


def path_for(leaves, m):
    n = len(leaves)
    if n == 1:
        return []
    k = split(n)
    if m < k:
        return path_for(leaves[:k], m) + [mth(leaves[k:])]
    return path_for(leaves[k:], m - k) + [mth(leaves[:k])]


def root_from_path(m, n, leaf_hash, path):
    """Iterative RFC 9162 style verification. Returns None if the proof shape is wrong."""
    if m >= n:
        return None
    fn, sn, r = m, n - 1, leaf_hash
    for p in path:
        if sn == 0:
            return None
        if fn & 1 or fn == sn:
            r = node_h(p, r)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = node_h(r, p)
        fn >>= 1
        sn >>= 1
    return r if sn == 0 else None


def file_leaf(path: str, digest_hex: str) -> bytes:
    b = path.encode("utf-8")
    return len(b).to_bytes(4, "big") + b + bytes.fromhex(digest_hex)


# ---- assignment -------------------------------------------------------------


def lp(b: bytes) -> bytes:
    return len(b).to_bytes(4, "big") + b


def words(seed: bytes, claim: str, role: str):
    prefix = b"dotsci/assign/v1" + lp(seed) + lp(claim.encode()) + lp(role.encode())
    block = 0
    while True:
        digest = sha(prefix + block.to_bytes(8, "big"))
        block += 1
        for i in range(4):
            yield int.from_bytes(digest[8 * i : 8 * i + 8], "big")


def below(it, n: int) -> int:
    limit = (1 << 64) - ((1 << 64) % n)
    while True:
        w = next(it)
        if w < limit:
            return w % n


def draw(seed: bytes, claim: str, role: str, candidates, count: int):
    pool = sorted(set(candidates))
    if len(seed) < 16 or count > len(pool):
        raise ValueError("invalid draw")
    it = words(seed, claim, role)
    out = []
    for i in range(count):
        j = i + below(it, len(pool) - i)
        pool[i], pool[j] = pool[j], pool[i]
        out.append(pool[i])
    return out


# ---- settlement -------------------------------------------------------------

B = 10_000


def bps(x: int, s: int) -> int:
    return x * s // B


def settle(c: dict, p: dict):
    kind = c["kind"]
    bounty, rs, cs = int(c["bounty"]), int(c["runner_stake"]), int(c["challenger_stake"])
    stakes = {k: int(v) for k, v in c["reviewer_stakes"].items()}
    votes = c["votes"]
    runner, challenger = c["runner"], c["challenger"]
    if kind not in ("unchallenged", "confirmed", "disputed", "spec_issue"):
        raise ValueError("invalid")
    if min([bounty, rs, cs, *stakes.values()]) < 0:
        raise ValueError("invalid")
    named = [x for x in [runner, challenger, *stakes] if x is not None]
    if len(named) != len(set(named)):
        raise ValueError("invalid")
    if kind in ("confirmed", "disputed") and challenger is None:
        raise ValueError("invalid")
    if kind in ("unchallenged", "spec_issue") and (challenger or cs):
        raise ValueError("invalid")

    pay: dict = {}

    def give(who, amt):
        pay[who] = pay.get(who, 0) + amt

    vault = treasury = 0
    verdict = "none"
    if kind == "unchallenged":
        give(runner, bounty + rs)
    elif kind == "spec_issue":
        paid = bps(bounty, p["spec_issue_pay_bps"])
        give(runner, paid + rs)
        vault = bounty - paid
    elif kind == "confirmed":
        reward = bps(bounty, p["confirm_reward_bps"])
        give(challenger, cs + reward)
        give(runner, bounty - reward + rs)
        verdict = "runner"
    else:
        if not stakes or set(votes) != set(stakes) or any(v not in ("runner", "challenger") for v in votes.values()):
            raise ValueError("invalid")
        fr = [r for r, v in votes.items() if v == "runner"]
        fc = [r for r, v in votes.items() if v == "challenger"]
        if len(fr) == len(fc):
            raise ArithmeticError("tie")
        verdict = "runner" if len(fr) > len(fc) else "challenger"
        majority, minority = (fr, fc) if verdict == "runner" else (fc, fr)
        pool = 0
        for r in minority:
            cut = bps(stakes[r], p["reviewer_slash_bps"])
            give(r, stakes[r] - cut)
            pool += cut
        if verdict == "runner":
            cut = bps(cs, p["challenger_slash_bps"])
            give(challenger, cs - cut)
            pool += cut
            winner, base = runner, bounty + rs
        else:
            cut = bps(rs, p["runner_slash_bps"])
            give(runner, rs - cut)
            pool += cut
            reward = bps(bounty, p["challenger_reward_bps"])
            vault = bounty - reward
            winner, base = challenger, cs + reward
        revs = bps(pool, p["reviewer_pool_bps"])
        each = revs // len(majority)
        treasury = revs - each * len(majority)
        for r in majority:
            give(r, stakes[r] + each)
        give(winner, base + (pool - revs))
    assert sum(pay.values()) + vault + treasury == bounty + rs + cs + sum(stakes.values())
    return verdict, pay, vault, treasury


# ---- replay -----------------------------------------------------------------

failures = []
checked = 0


def expect(ok: bool, what: str):
    global checked
    checked += 1
    if not ok:
        failures.append(what)


def run():
    for case in load("manifest-hash.json")["cases"]:
        text = canonical(case["manifest"])
        expect(text == case["canonical"], f"manifest {case['name']}: canonical text")
        expect(sha(text.encode("utf-8")).hex() == case["sha256"], f"manifest {case['name']}: hash")

    m = load("merkle.json")
    for t in m["trees"]:
        leaves = [bytes.fromhex(x) for x in t["leaves"]]
        expect(mth(leaves).hex() == t["root"], f"tree {t['name']}: root")
        for i, expected in enumerate(t["audit_paths"]):
            expect([x.hex() for x in path_for(leaves, i)] == expected, f"tree {t['name']}: path {i}")
            got = root_from_path(i, len(leaves), leaf_h(leaves[i]), [bytes.fromhex(x) for x in expected])
            expect(got is not None and got.hex() == t["root"], f"tree {t['name']}: verify {i}")
    for c in m["inclusion"]:
        got = root_from_path(c["index"], c["size"], leaf_h(bytes.fromhex(c["leaf"])), [bytes.fromhex(x) for x in c["siblings"]])
        ok = got is not None and got.hex() == c["root"]
        expect(ok == c["valid"], f"inclusion {c['name']}: expected valid={c['valid']}")
    for f in m["files"]:
        ordered = sorted(((p, d.lower()) for p, d in f["input"].items()), key=lambda x: x[0].encode("utf-8"))
        expect([p for p, _ in ordered] == f["order"], f"files {f['name']}: order")
        leaves = [file_leaf(p, d) for p, d in ordered]
        expect([x.hex() for x in leaves] == f["leaves"], f"files {f['name']}: leaves")
        expect(mth(leaves).hex() == f["root"] and len(leaves) == f["size"], f"files {f['name']}: root")
        for pr in f["proofs"]:
            got = root_from_path(pr["index"], f["size"], leaf_h(leaves[pr["index"]]), [bytes.fromhex(x) for x in pr["siblings"]])
            expect(got is not None and got.hex() == f["root"], f"files {f['name']}: proof {pr['path']}")

    a = load("assignment.json")
    for s in a["streams"]:
        it = words(bytes.fromhex(s["seed"]), s["claim_id"], s["role"])
        expect([str(next(it)) for _ in s["words"]] == s["words"], f"stream {s['claim_id']!r}/{s['role']!r}")
    for u in a["uniform_below"]:
        it = iter(int(w) for w in u["words"])
        expect(str(below(it, int(u["n"]))) == u["result"], f"uniform_below n={u['n']}")
    for d in a["draws"]:
        got = draw(bytes.fromhex(d["seed"]), d["claim_id"], d["role"], d["candidates"], d["count"])
        expect(got == d["picks"], f"draw {d['claim_id']}/{d['role']}")
    for e in a["errors"]:
        try:
            draw(bytes.fromhex(e["seed"]), e["claim_id"], e["role"], e["candidates"], e["count"])
            expect(False, f"error vector {e['name']} did not fail")
        except ValueError:
            expect(True, "")

    s = load("settlement.json")
    for c in s["cases"]:
        params = s["params"][c["params"]]
        if "error" in c:
            try:
                settle(c["case"], params)
                expect(False, f"settlement {c['name']}: expected {c['error']}")
            except ArithmeticError:
                expect(c["error"] == "tie", f"settlement {c['name']}: tie")
            except ValueError:
                expect(c["error"] == "invalid", f"settlement {c['name']}: invalid")
            continue
        verdict, pay, vault, treasury = settle(c["case"], params)
        e = c["expected"]
        expect(verdict == e["verdict"], f"settlement {c['name']}: verdict")
        expect({k: str(v) for k, v in sorted(pay.items())} == e["payouts"], f"settlement {c['name']}: payouts")
        expect(str(vault) == e["to_vault"] and str(treasury) == e["to_treasury"], f"settlement {c['name']}: vault/treasury")


if __name__ == "__main__":
    run()
    if failures:
        print(f"{len(failures)} of {checked} checks failed:", file=sys.stderr)
        for f in failures[:40]:
            print(" -", f, file=sys.stderr)
        sys.exit(1)
    print(f"ok: {checked} checks reproduced from the vectors")

// Replays the shared conformance vectors in spec/vectors with the JavaScript implementation.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  sha256, toHex, fromHex, utf8, canonicalizeText, manifestHash,
  leafHash, merkleRoot, auditPath, verifyInclusion, fileLeaf, commitFiles, proveFile, verifyFileProof, CommitError,
  Stream, uniformBelow, draw, verifyDraw, AssignmentError,
  settle, SettlementError, TieError,
} from "../src/index.js";

const dir = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "spec", "vectors");
const load = (name) => JSON.parse(readFileSync(join(dir, name), "utf8"));

test("manifest hash vectors", () => {
  const { cases } = load("manifest-hash.json");
  assert.ok(cases.length >= 10);
  for (const c of cases) {
    assert.equal(canonicalizeText(c.text), c.canonical, c.name);
    assert.equal(manifestHash(c.text), c.sha256, c.name);
  }
});

test("json number vectors", () => {
  const { cases, rejected } = load("json-numbers.json");
  assert.ok(cases.length > 150);
  for (const c of cases) assert.equal(canonicalizeText(c.lexeme), c.canonical, c.lexeme);
  for (const lex of rejected) assert.throws(() => canonicalizeText(lex), /out of range/, lex);
});

const bytes = (hexes) => hexes.map(fromHex);

test("merkle trees and audit paths", () => {
  for (const t of load("merkle.json").trees) {
    const leaves = bytes(t.leaves);
    assert.equal(toHex(merkleRoot(leaves)), t.root, t.name);
    t.audit_paths.forEach((expected, i) => {
      assert.deepEqual(auditPath(leaves, i).map(toHex), expected, `${t.name} path ${i}`);
      assert.ok(verifyInclusion(fromHex(t.root), leaves.length, i, leaves[i], bytes(expected)), `${t.name} verify ${i}`);
    });
  }
});

test("inclusion verdicts, valid and invalid", () => {
  const { inclusion } = load("merkle.json");
  assert.ok(inclusion.some((c) => c.valid) && inclusion.some((c) => !c.valid));
  for (const c of inclusion) {
    assert.equal(verifyInclusion(fromHex(c.root), c.size, c.index, fromHex(c.leaf), bytes(c.siblings)), c.valid, c.name);
  }
});

test("file commitments", () => {
  for (const f of load("merkle.json").files) {
    const commitment = commitFiles(f.input);
    assert.deepEqual(commitment.files.map(([p]) => p), f.order, f.name);
    assert.deepEqual(commitment.leaves.map(toHex), f.leaves, f.name);
    assert.equal(commitment.root, f.root, f.name);
    assert.equal(commitment.size, f.size, f.name);
    for (const proof of f.proofs) {
      const built = proveFile(commitment, proof.path);
      assert.equal(built.index, proof.index);
      assert.deepEqual(built.siblings, proof.siblings);
      assert.ok(verifyFileProof(built, f.root), `${f.name} ${proof.path}`);
    }
  }
});

test("file proofs fail for the wrong file, root or path", () => {
  const c = commitFiles({ "a.txt": "aa".repeat(32), "b.txt": "bb".repeat(32), "c.txt": "cc".repeat(32) });
  const proof = proveFile(c, "b.txt");
  assert.ok(verifyFileProof(proof, c.root));
  assert.ok(verifyFileProof(proof, "0x" + c.root));
  assert.ok(!verifyFileProof({ ...proof, sha256: "dd".repeat(32) }, c.root));
  assert.ok(!verifyFileProof({ ...proof, path: "x.txt" }, c.root));
  assert.ok(!verifyFileProof({ ...proof, index: 0 }, c.root));
  assert.ok(!verifyFileProof(proof, "11".repeat(32)));
  assert.ok(!verifyFileProof({ ...proof, path: "../b.txt" }, c.root));
  assert.ok(!verifyFileProof({ ...proof, siblings: ["zz"] }, c.root));
  assert.throws(() => proveFile(c, "missing"), CommitError);
});

test("path validation matches the reference", () => {
  for (const bad of ["", "/abs", "a/../b", "..", "a//b", "a/./b", "a/", "a\\b", "./a"]) {
    assert.throws(() => commitFiles({ [bad]: "00".repeat(32) }), CommitError, JSON.stringify(bad));
  }
  assert.doesNotThrow(() => commitFiles({ "a/b/c.txt": "00".repeat(32), "é": "11".repeat(32) }));
  assert.throws(() => fileLeaf("x", "abc"), CommitError);
});

test("assignment streams", () => {
  for (const s of load("assignment.json").streams) {
    const stream = new Stream(fromHex(s.seed), s.claim_id, s.role);
    assert.deepEqual(s.words.map(() => String(stream.nextWord())), s.words);
  }
});

test("uniform_below rejection sampling", () => {
  for (const u of load("assignment.json").uniform_below) {
    const words = u.words.map(BigInt);
    let i = 0;
    assert.equal(String(uniformBelow(() => words[i++], BigInt(u.n))), u.result, `n=${u.n}`);
  }
});

test("draws", () => {
  const { draws, errors } = load("assignment.json");
  for (const d of draws) {
    assert.deepEqual(draw(fromHex(d.seed), d.claim_id, d.role, d.candidates, d.count), d.picks);
    assert.ok(verifyDraw(fromHex(d.seed), d.claim_id, d.role, d.candidates, d.picks));
  }
  for (const e of errors) assert.throws(() => draw(fromHex(e.seed), e.claim_id, e.role, e.candidates, e.count), AssignmentError, e.name);
});

test("a changed pick fails verification", () => {
  const d = load("assignment.json").draws.find((x) => x.picks.length >= 2);
  const seed = fromHex(d.seed);
  assert.ok(!verifyDraw(seed, d.claim_id, d.role, d.candidates, [...d.picks].reverse().concat([])) || d.picks.length < 2 || new Set(d.picks).size < 2);
  assert.ok(!verifyDraw(seed, d.claim_id, d.role, d.candidates, [d.picks[0] + "x"]));
  assert.ok(!verifyDraw(seed.slice(0, 8), d.claim_id, d.role, d.candidates, d.picks));
});

test("settlement vectors", () => {
  const vectors = load("settlement.json");
  assert.ok(vectors.cases.length > 100);
  for (const c of vectors.cases) {
    const params = vectors.params[c.params];
    if (c.error === "tie") assert.throws(() => settle(c.case, params), TieError, c.name);
    else if (c.error === "invalid") assert.throws(() => settle(c.case, params), (e) => e instanceof SettlementError && !(e instanceof TieError), c.name);
    else {
      const got = settle(c.case, params);
      const e = c.expected;
      assert.equal(got.verdict, e.verdict, c.name);
      const payouts = Object.fromEntries(Object.entries(got.payouts).sort().map(([k, v]) => [k, String(v)]));
      assert.deepEqual(payouts, e.payouts, c.name);
      assert.equal(String(got.toVault), e.to_vault, c.name);
      assert.equal(String(got.toTreasury), e.to_treasury, c.name);
    }
  }
});

test("settlement rejects out of range parameters", () => {
  const base = load("settlement.json").params.mid;
  const kase = { kind: "unchallenged", bounty: "1", runner: "r", runner_stake: "0", challenger: null, challenger_stake: "0", reviewer_stakes: {}, votes: {} };
  assert.throws(() => settle(kase, { ...base, runner_slash_bps: 10001 }), SettlementError);
  assert.throws(() => settle(kase, { ...base, runner_slash_bps: -1 }), SettlementError);
  assert.throws(() => settle(kase, { ...base, runner_slash_bps: "x" }), SettlementError);
  const { runner_slash_bps, ...missing } = base;
  assert.throws(() => settle(kase, missing), SettlementError);
});

test("sha256 and leafHash agree with the RFC 6962 definition", () => {
  assert.equal(toHex(leafHash(new Uint8Array(0))), toHex(sha256(new Uint8Array([0]))));
  assert.equal(utf8("é").length, 2);
});

import test from "node:test";
import assert from "node:assert/strict";
import { runColony, leaderboard, netAt, dotStateAt, verifyDraw, fromHex, sha256, utf8, toHex } from "../src/index.js";

const world = runColony({ seed: "dotsci", agents: 24, claims: 12 });
const big = runColony({ seed: "big", agents: 80, claims: 60 });

const digest = (obj) => toHex(sha256(utf8(JSON.stringify(obj))));

test("same seed gives the same world, a different seed gives another", () => {
  assert.equal(digest(runColony({ seed: "dotsci", agents: 24, claims: 12 })), digest(world));
  assert.notEqual(digest(runColony({ seed: "dotsci2", agents: 24, claims: 12 })), digest(world));
});

test("golden digest of the default world", () => {
  // Update this deliberately if the simulation changes. It exists to catch accidents.
  assert.equal(digest(world), "6c7e59c6fa35043e058726f792d9b7a1206a3aa4262725f57b021f105bacff8d");
});

test("output is plain data and says it is a simulation", () => {
  assert.doesNotThrow(() => JSON.stringify(world));
  assert.equal(world.simulated, true);
  assert.ok(world.events.filter((e) => e.type === "claim_listed").every((e) => e.data.simulated === true));
});

test("value is conserved across many seeds and sizes", () => {
  for (let i = 0; i < 60; i++) {
    const c = runColony({ seed: `s${i}`, agents: 6 + (i % 30), claims: 1 + (i % 25) });
    assert.ok(c.invariant.holds, `seed s${i}`);
    assert.equal(c.invariant.start, c.invariant.end);
    const sum = c.agents.reduce((a, x) => a + BigInt(x.balance), 0n) + BigInt(c.vault) + BigInt(c.treasury);
    assert.equal(String(sum), c.invariant.end);
    assert.ok(c.agents.every((a) => BigInt(a.balance) >= 0n));
  }
});

test("every settlement conserves its own claim", () => {
  const byClaim = new Map(big.claims.map((c) => [c.id, c]));
  for (const e of big.events.filter((x) => x.type === "settled")) {
    const claim = byClaim.get(e.claim);
    const bounty = BigInt(claim.bounty);
    const stake = bounty / 10n;
    const reviewer = bounty / 20n;
    let totalIn = bounty + stake;
    if (claim.challenger && (e.data.kind === "disputed" || e.data.kind === "confirmed")) totalIn += stake;
    if (e.data.kind === "disputed") totalIn += reviewer * BigInt(claim.panel.length);
    const out = Object.values(e.data.payouts).reduce((a, v) => a + BigInt(v), 0n) + BigInt(e.data.to_vault) + BigInt(e.data.to_treasury);
    assert.equal(out, totalIn, e.claim);
  }
});

test("every runner, challenger and reviewer draw can be re-verified", () => {
  const seed = fromHex(big.seedHex);
  let checked = 0;
  for (const e of big.events) {
    if (e.type === "runner_assigned") {
      assert.ok(verifyDraw(seed, e.claim, "runner", e.data.candidates, [e.data.pick]));
      checked++;
    }
    if (e.type === "panel_drawn") {
      assert.ok(verifyDraw(seed, e.claim, "reviewer", e.data.candidates, e.data.picks));
      checked++;
    }
  }
  assert.ok(checked > 40);
  const e = big.events.find((x) => x.type === "runner_assigned");
  assert.ok(!verifyDraw(seed, e.claim, "runner", e.data.candidates, [e.data.candidates.find((c) => c !== e.data.pick)]));
});

test("nobody holds two roles on a claim and operators stay independent", () => {
  const ops = new Map(big.agents.map((a) => [a.id, a.operator]));
  const submitters = new Map(big.claims.map((c) => [c.id, c.submitter]));
  for (const c of big.claims.filter((x) => x.status === "settled")) {
    const roles = [c.runner, c.challenger, ...c.panel].filter(Boolean);
    assert.equal(new Set(roles).size, roles.length, c.id);
    assert.notEqual(ops.get(c.runner), ops.get(submitters.get(c.id)), `${c.id} runner shares the submitter's operator`);
    if (c.challenger) assert.notEqual(ops.get(c.challenger), ops.get(c.runner), `${c.id} challenger shares the runner's operator`);
    for (const r of c.panel) {
      assert.notEqual(ops.get(r), ops.get(c.runner));
      assert.notEqual(ops.get(r), ops.get(c.challenger));
      assert.notEqual(ops.get(r), ops.get(submitters.get(c.id)));
    }
    if (c.panel.length) assert.equal(c.panel.length % 2, 1, "panels are odd so votes cannot tie");
  }
});

test("disputed verdicts follow the votes", () => {
  const votes = new Map();
  for (const e of big.events) if (e.type === "vote") votes.set(e.claim, [...(votes.get(e.claim) ?? []), e.data.vote]);
  let disputes = 0;
  for (const e of big.events.filter((x) => x.type === "settled" && x.data.kind === "disputed")) {
    const v = votes.get(e.claim);
    const forRunner = v.filter((x) => x === "runner").length;
    assert.equal(e.data.verdict, forRunner > v.length - forRunner ? "runner" : "challenger", e.claim);
    disputes++;
  }
  assert.ok(disputes >= 1, "the big world contains a dispute");
});

test("events are ordered, uniquely named, and tell the full story", () => {
  const ids = new Set();
  let last = -1;
  for (const e of big.events) {
    assert.ok(e.t >= last);
    last = e.t;
    assert.ok(!ids.has(e.id));
    ids.add(e.id);
  }
  const kinds = new Set(big.events.map((e) => e.type));
  for (const k of ["claim_listed", "runner_assigned", "run_completed", "settled", "challenged", "panel_drawn", "vote"]) assert.ok(kinds.has(k), k);
  for (const c of big.claims.filter((x) => x.status === "settled")) {
    const mine = big.events.filter((e) => e.claim === c.id).map((e) => e.type);
    assert.equal(mine[0], "claim_listed");
    assert.equal(mine.at(-1), "settled");
  }
});

test("stats add up", () => {
  const settled = big.claims.filter((c) => c.status === "settled");
  const runs = big.agents.reduce((a, x) => a + x.stats.runs, 0);
  assert.equal(runs, settled.length);
  const outcomes = big.agents.reduce((a, x) => a + x.stats.reproduced + x.stats.notReproduced + x.stats.specIssues, 0);
  assert.equal(outcomes, settled.length);
});

test("leaderboard is sorted by net and stable", () => {
  const board = leaderboard(big);
  for (let i = 1; i < board.length; i++) assert.ok(BigInt(board[i - 1].net) >= BigInt(board[i].net));
  assert.deepEqual(board.map((a) => a.id), leaderboard(big).map((a) => a.id));
});

test("dot state follows what the agent is doing", () => {
  const run = big.events.findIndex((e) => e.type === "runner_assigned");
  const runner = big.events[run].agents[0];
  assert.equal(dotStateAt(big, runner, run), "running");
  assert.equal(dotStateAt(big, runner, -1), "idle");
  const panel = big.events.findIndex((e) => e.type === "panel_drawn");
  assert.equal(dotStateAt(big, big.events[panel].agents[0], panel), "reviewing");
  const ch = big.events.findIndex((e) => e.type === "challenged");
  assert.equal(dotStateAt(big, big.events[ch].agents[0], ch), "challenging");
});

test("rejects out of range options", () => {
  for (const bad of [{ agents: 5 }, { agents: 201 }, { agents: 7.5 }, { claims: 0 }, { claims: 201 }]) assert.throws(() => runColony(bad), RangeError);
});

test("standings at a point in the replay build up to the final result", () => {
  const start = netAt(big, -1);
  assert.ok(Object.values(start).every((v) => v === "0"));
  const end = netAt(big, big.events.length - 1);
  for (const a of big.agents) assert.equal(end[a.id], a.net, a.id);
  const mid = netAt(big, Math.floor(big.events.length / 2));
  assert.notDeepEqual(mid, start);
  assert.notDeepEqual(mid, end);
  assert.equal(Object.values(end).reduce((a, v) => a + BigInt(v), 0n) + BigInt(big.vault) + BigInt(big.treasury) - BigInt(big.claims.reduce((a, c) => a + BigInt(c.bounty), 0n)), 0n);
});

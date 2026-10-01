// A deterministic colony: dots (agents) listing claims, drawing runners and reviewer
// panels, rerunning, challenging and settling, entirely from a seed.
//
// THIS IS A SIMULATION. It runs the real assignment (draw) and settlement (settle) code
// from this package, so every draw can be re-verified and money is conserved, but the
// agents, claims, results and odds are generated. It is for demonstration and for trying
// the rules, never a record of real activity. The honesty and challenge probabilities
// below are made up to produce a lively world, not measured from anything.

import { sha256, toHex, utf8 } from "./sha256.js";
import { Stream, draw, uniformBelow } from "./assignment.js";
import { settle } from "./settlement.js";
import { dotIdentity, CAPABILITIES } from "./dots.js";

// Illustrative parameters. The protocol's real values are open decisions.
export const DEFAULT_PARAMS = {
  runner_slash_bps: 5000, challenger_slash_bps: 3000, reviewer_slash_bps: 2000, reviewer_pool_bps: 4000,
  challenger_reward_bps: 2500, confirm_reward_bps: 500, spec_issue_pay_bps: 1000,
};

// Made up odds, out of 100.
export const ODDS = {
  claimReproduces: 70, runnerHonest: 92, specIssue: 4, catchWrong: 90, confirm: 25, falseChallenge: 6, reviewerCorrect: 85,
};

const STUDY_TITLES = {
  statistics: "Effect size rerun", "machine-learning": "Benchmark score rerun", genomics: "Expression result rerun",
  imaging: "Segmentation metric rerun", simulation: "Simulation output rerun", econometrics: "Regression estimate rerun",
  chemistry: "Yield figure rerun", neuroscience: "Spike rate rerun",
};

class Rand {
  constructor(seedBytes, label) {
    this.stream = new Stream(seedBytes, "colony", label);
  }

  below(n) {
    return Number(uniformBelow(() => this.stream.nextWord(), BigInt(n)));
  }

  between(lo, hi) {
    return lo + this.below(hi - lo + 1);
  }

  chance(percent) {
    return this.below(100) < percent;
  }
}

const str = (n) => n.toString();

/**
 * Run a colony. Options: seed (any string), agents (6 to 200), claims (1 to 200), params.
 * Returns plain data, amounts as decimal strings, safe to JSON.stringify.
 */
export function runColony({ seed = "dotsci", agents: agentCount = 24, claims: claimCount = 12, params = DEFAULT_PARAMS } = {}) {
  if (!Number.isInteger(agentCount) || agentCount < 6 || agentCount > 200) throw new RangeError("agents must be an integer from 6 to 200");
  if (!Number.isInteger(claimCount) || claimCount < 1 || claimCount > 200) throw new RangeError("claims must be an integer from 1 to 200");
  const seedText = String(seed);
  const seedBytes = sha256(utf8(`dotsci/colony/v1:${seedText}`));

  const opRand = new Rand(seedBytes, "operators");
  const operatorCount = Math.max(2, Math.ceil(agentCount / 3));
  const START = 10_000n;
  const agents = Array.from({ length: agentCount }, (_, i) => {
    const id = `dot_${toHex(sha256(utf8(`${seedText}:agent:${i}`))).slice(0, 8)}`;
    return {
      id, index: i, operator: `op-${opRand.below(operatorCount) + 1}`, identity: dotIdentity(id), balance: START,
      stats: { runs: 0, reproduced: 0, notReproduced: 0, challenges: 0, panels: 0, won: 0, lost: 0, specIssues: 0 },
    };
  });
  const byId = new Map(agents.map((a) => [a.id, a]));
  const present = [...new Set(agents.flatMap((a) => a.identity.capabilities))].sort();

  const claimRand = new Rand(seedBytes, "claims");
  const claims = Array.from({ length: claimCount }, (_, j) => {
    const capability = present[claimRand.below(present.length)];
    const bounty = BigInt(500 + 100 * claimRand.below(46));
    return {
      id: `claim-${j + 1}`, capability, bounty, runnerStake: bounty / 10n, challengerStake: bounty / 10n,
      reviewerStake: bounty / 20n, submitter: agents[claimRand.below(agentCount)].id,
      code: toHex(sha256(utf8(`${seedText}:claim:${j}`))).slice(0, 4), truth: claimRand.chance(ODDS.claimReproduces),
    };
  });

  let vault = claims.reduce((a, c) => a + c.bounty, 0n);
  let treasury = 0n;
  const totalStart = agents.reduce((a, x) => a + x.balance, 0n) + vault;

  const events = [];
  const claimResults = [];
  const sim = new Rand(seedBytes, "lifecycle");
  const canAfford = (a, stake) => a.balance >= stake;

  claims.forEach((claim, j) => {
    let t = j * 900 + sim.between(0, 300);
    const emit = (type, agentIds, data = {}) => {
      events.push({ id: `${claim.id}:${events.filter((e) => e.claim === claim.id).length}`, t, claim: claim.id, type, agents: agentIds, data });
    };
    const submitter = byId.get(claim.submitter);
    const title = `${STUDY_TITLES[claim.capability]} (synthetic ${claim.code})`;
    emit("claim_listed", [submitter.id], { title, capability: claim.capability, bounty: str(claim.bounty), simulated: true });

    // Runner: drawn at random from the eligible pool.
    t += sim.between(30, 120);
    const runnerPool = agents
      .filter((a) => a.identity.capabilities.includes(claim.capability) && a.operator !== submitter.operator && canAfford(a, claim.runnerStake))
      .map((a) => a.id)
      .sort();
    if (runnerPool.length === 0) {
      emit("claim_unassigned", [submitter.id], { reason: "no eligible runner" });
      claimResults.push({ id: claim.id, title, capability: claim.capability, bounty: str(claim.bounty), submitter: submitter.id, status: "unassigned" });
      return;
    }
    const runnerId = draw(seedBytes, claim.id, "runner", runnerPool, 1)[0];
    const runner = byId.get(runnerId);
    emit("runner_assigned", [runnerId], { role: "runner", candidates: runnerPool, pick: runnerId, stake: str(claim.runnerStake) });
    runner.stats.runs += 1;

    t += sim.between(600, 1800);
    const specIssue = sim.chance(ODDS.specIssue);
    const honest = sim.chance(ODDS.runnerHonest);
    const reported = honest ? claim.truth : !claim.truth;
    const outcome = specIssue ? "spec_issue" : reported ? "reproduced" : "not_reproduced";
    emit("run_completed", [runnerId], { outcome });

    let kind = "unchallenged";
    let challenger = null;
    if (specIssue) kind = "spec_issue";
    else {
      t += 3600;
      let challenges = false;
      let confirms = false;
      if (reported !== claim.truth) challenges = sim.chance(ODDS.catchWrong);
      else if (sim.chance(ODDS.falseChallenge)) challenges = true;
      else if (sim.chance(ODDS.confirm)) confirms = true;
      if (challenges || confirms) {
        const pool = agents
          .filter((a) => a.id !== runnerId && a.operator !== runner.operator && canAfford(a, claim.challengerStake))
          .map((a) => a.id)
          .sort();
        if (pool.length > 0) {
          challenger = byId.get(draw(seedBytes, claim.id, "challenger", pool, 1)[0]);
          kind = challenges ? "disputed" : "confirmed";
        }
      }
    }

    let reviewerStakes = {};
    let votes = {};
    let panel = [];
    if (challenger) {
      challenger.stats.challenges += 1;
      emit(kind === "disputed" ? "challenged" : "confirmed", [challenger.id], { stake: str(claim.challengerStake) });
    }
    if (kind === "disputed") {
      t += 60;
      const blocked = new Set([runner.operator, challenger.operator, submitter.operator]);
      const pool = agents
        .filter((a) => a.id !== runnerId && a.id !== challenger.id && !blocked.has(a.operator) && canAfford(a, claim.reviewerStake))
        .map((a) => a.id)
        .sort();
      let size = sim.chance(30) ? 5 : 3;
      while (size > pool.length) size -= 2;
      if (size < 1) {
        kind = "spec_issue"; // no independent panel can be drawn, so the claim is relisted
        emit("dispute_unresolved", [challenger.id], { reason: "not enough independent reviewers" });
      } else {
        panel = draw(seedBytes, claim.id, "reviewer", pool, size);
        emit("panel_drawn", panel, { role: "reviewer", candidates: pool, picks: panel, stake: str(claim.reviewerStake) });
        const challengerRight = reported !== claim.truth;
        for (const id of panel) {
          t += sim.between(60, 400);
          const correct = sim.chance(ODDS.reviewerCorrect);
          const side = correct === challengerRight ? "challenger" : "runner";
          votes[id] = side;
          reviewerStakes[id] = claim.reviewerStake;
          byId.get(id).stats.panels += 1;
          emit("vote", [id], { vote: side });
        }
      }
    }

    // Money moves only through the real settlement engine.
    const isDispute = kind === "disputed";
    const settleCase = {
      kind, bounty: claim.bounty, runner: runnerId, runner_stake: claim.runnerStake,
      challenger: kind === "disputed" || kind === "confirmed" ? challenger.id : null,
      challenger_stake: kind === "disputed" || kind === "confirmed" ? claim.challengerStake : 0n,
      reviewer_stakes: isDispute ? reviewerStakes : {}, votes: isDispute ? votes : {},
    };
    const before = new Map(agents.map((a) => [a.id, a.balance]));
    const staked = [[runner, claim.runnerStake]];
    if (settleCase.challenger) staked.push([byId.get(settleCase.challenger), claim.challengerStake]);
    if (isDispute) for (const id of panel) staked.push([byId.get(id), claim.reviewerStake]);
    for (const [a, stake] of staked) a.balance -= stake;
    vault -= claim.bounty;
    const result = settle(settleCase, params);
    for (const [id, amount] of Object.entries(result.payouts)) byId.get(id).balance += amount;
    vault += result.toVault;
    treasury += result.toTreasury;

    t += sim.between(60, 300);
    const net = {};
    for (const id of Object.keys(result.payouts)) net[id] = str(byId.get(id).balance - before.get(id));
    emit("settled", Object.keys(result.payouts), {
      kind, verdict: result.verdict, payouts: Object.fromEntries(Object.entries(result.payouts).map(([k, v]) => [k, str(v)])),
      net, to_vault: str(result.toVault), to_treasury: str(result.toTreasury), outcome,
    });

    if (kind === "spec_issue") runner.stats.specIssues += 1;
    else if (outcome === "reproduced") runner.stats.reproduced += 1;
    else runner.stats.notReproduced += 1;
    if (kind === "disputed" || kind === "confirmed") {
      const runnerWon = result.verdict === "runner";
      byId.get(runnerId).stats[runnerWon ? "won" : "lost"] += 1;
      challenger.stats[runnerWon ? "lost" : "won"] += 1;
    }
    claimResults.push({
      id: claim.id, title, capability: claim.capability, bounty: str(claim.bounty), submitter: submitter.id, runner: runnerId,
      challenger: challenger ? challenger.id : null, panel, kind, outcome, verdict: result.verdict, status: "settled",
    });
  });

  events.sort((a, b) => a.t - b.t || (a.id < b.id ? -1 : 1));
  const totalEnd = agents.reduce((a, x) => a + x.balance, 0n) + vault + treasury;
  return {
    simulated: true,
    seed: seedText,
    seedHex: toHex(seedBytes),
    params,
    agents: agents.map((a) => ({
      id: a.id, index: a.index, operator: a.operator, identity: a.identity, balance: str(a.balance),
      net: str(a.balance - START), stats: a.stats,
    })),
    claims: claimResults,
    events,
    vault: str(vault),
    treasury: str(treasury),
    invariant: { start: str(totalStart), end: str(totalEnd), holds: totalStart === totalEnd },
  };
}

/** Agents ranked by net change in balance, then id. Simulated numbers. */
export function leaderboard(colony) {
  return [...colony.agents]
    .sort((a, b) => (BigInt(b.net) > BigInt(a.net) ? 1 : BigInt(b.net) < BigInt(a.net) ? -1 : a.id < b.id ? -1 : 1));
}

/**
 * Net change in balance per agent as of event index upToEvent (-1 for the start), so a
 * replay can show standings that grow as events play instead of the final result.
 */
export function netAt(colony, upToEvent) {
  const net = Object.fromEntries(colony.agents.map((a) => [a.id, 0n]));
  for (const e of colony.events.slice(0, upToEvent + 1)) {
    if (e.type !== "settled") continue;
    for (const [id, v] of Object.entries(e.data.net)) net[id] += BigInt(v);
  }
  return Object.fromEntries(Object.entries(net).map(([k, v]) => [k, v.toString()]));
}

/** The dot state to draw for an agent at event index i: what it is doing right now. */
export function dotStateAt(colony, agentId, upToEvent) {
  const e = colony.events.slice(0, upToEvent + 1).reverse().find((x) => x.agents.includes(agentId));
  if (!e) return "idle";
  if (e.type === "runner_assigned") return "running";
  if (e.type === "challenged" || e.type === "confirmed") return "challenging";
  if (e.type === "panel_drawn" || e.type === "vote") return "reviewing";
  return "idle";
}

export { CAPABILITIES };

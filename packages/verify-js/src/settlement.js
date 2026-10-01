// Integer settlement engine in basis points. All amounts are BigInt, so uint256 values are exact.
// Mirrors packages/protocol/src/dotsci_protocol/settlement.py.
// Parameters are required arguments: the real values are open decisions.

export const BPS = 10000n;

export class SettlementError extends Error {}
export class TieError extends SettlementError {}

const PARAM_NAMES = [
  "runner_slash_bps", "challenger_slash_bps", "reviewer_slash_bps", "reviewer_pool_bps",
  "challenger_reward_bps", "confirm_reward_bps", "spec_issue_pay_bps",
];

/** Validate and convert parameters (numbers, strings or BigInt) to BigInt basis points. */
export function params(input) {
  const out = {};
  for (const name of PARAM_NAMES) {
    let v;
    try { v = BigInt(input[name]); } catch { throw new SettlementError(`${name} must be an integer between 0 and 10000`); }
    if (v < 0n || v > BPS) throw new SettlementError(`${name} must be an integer between 0 and 10000`);
    out[name] = v;
  }
  return out;
}

const bps = (amount, share) => (amount * share) / BPS; // BigInt division floors for non-negative values

function amountOf(v) {
  let n;
  try { n = BigInt(v); } catch { throw new SettlementError("amounts must be non-negative integers"); }
  if (n < 0n) throw new SettlementError("amounts must be non-negative integers");
  return n;
}

/**
 * Settle one case. case_ fields: kind, bounty, runner, runner_stake, challenger, challenger_stake,
 * reviewer_stakes ({id: amount}), votes ({id: "runner"|"challenger"}). Amounts may be decimal strings.
 * Returns { verdict, payouts: {id: BigInt}, toVault, toTreasury }.
 */
export function settle(case_, rawParams) {
  const p = params(rawParams);
  const kind = case_.kind;
  const bounty = amountOf(case_.bounty);
  const runnerStake = amountOf(case_.runner_stake ?? 0);
  const challengerStake = amountOf(case_.challenger_stake ?? 0);
  const stakes = {};
  for (const [id, v] of Object.entries(case_.reviewer_stakes ?? {})) stakes[id] = amountOf(v);
  const votes = case_.votes ?? {};
  const { runner, challenger } = case_;

  if (!["unchallenged", "confirmed", "disputed", "spec_issue"].includes(kind)) throw new SettlementError(`unknown case kind: ${kind}`);
  const named = [runner, challenger, ...Object.keys(stakes)].filter((x) => x !== null && x !== undefined);
  if (new Set(named).size !== named.length) throw new SettlementError("one agent cannot hold more than one role on a claim");
  if ((kind === "confirmed" || kind === "disputed") && (challenger === null || challenger === undefined)) {
    throw new SettlementError(`a ${kind} case needs a challenger`);
  }
  if ((kind === "unchallenged" || kind === "spec_issue") && (challenger || challengerStake)) {
    throw new SettlementError(`a ${kind} case has no challenger`);
  }

  const payouts = {};
  const give = (who, amount) => { payouts[who] = (payouts[who] ?? 0n) + amount; };
  let toVault = 0n;
  let toTreasury = 0n;
  let verdict = "none";

  if (kind === "unchallenged") {
    give(runner, bounty + runnerStake);
  } else if (kind === "spec_issue") {
    const paid = bps(bounty, p.spec_issue_pay_bps);
    give(runner, paid + runnerStake);
    toVault += bounty - paid;
  } else if (kind === "confirmed") {
    const reward = bps(bounty, p.confirm_reward_bps);
    give(challenger, challengerStake + reward);
    give(runner, bounty - reward + runnerStake);
    verdict = "runner";
  } else {
    const ids = Object.keys(stakes);
    if (ids.length === 0) throw new SettlementError("a disputed case needs reviewers");
    const voters = Object.keys(votes);
    if (voters.length !== ids.length || !voters.every((v) => v in stakes)) throw new SettlementError("every reviewer must have voted, and only reviewers can vote");
    if (Object.values(votes).some((v) => v !== "runner" && v !== "challenger")) throw new SettlementError("votes must be 'runner' or 'challenger'");
    const forRunner = voters.filter((r) => votes[r] === "runner");
    const forChallenger = voters.filter((r) => votes[r] === "challenger");
    if (forRunner.length === forChallenger.length) throw new TieError("reviewers are split evenly");
    verdict = forRunner.length > forChallenger.length ? "runner" : "challenger";
    const majority = verdict === "runner" ? forRunner : forChallenger;
    const minority = verdict === "runner" ? forChallenger : forRunner;

    let pool = 0n;
    for (const r of minority) {
      const cut = bps(stakes[r], p.reviewer_slash_bps);
      give(r, stakes[r] - cut);
      pool += cut;
    }
    let winner;
    let winnerBase;
    if (verdict === "runner") {
      const cut = bps(challengerStake, p.challenger_slash_bps);
      give(challenger, challengerStake - cut);
      pool += cut;
      winner = runner;
      winnerBase = bounty + runnerStake;
    } else {
      const cut = bps(runnerStake, p.runner_slash_bps);
      give(runner, runnerStake - cut);
      pool += cut;
      const reward = bps(bounty, p.challenger_reward_bps);
      toVault += bounty - reward;
      winner = challenger;
      winnerBase = challengerStake + reward;
    }
    const reviewersTotal = bps(pool, p.reviewer_pool_bps);
    const each = reviewersTotal / BigInt(majority.length);
    toTreasury += reviewersTotal - each * BigInt(majority.length);
    for (const r of majority) give(r, stakes[r] + each);
    give(winner, winnerBase + (pool - reviewersTotal));
  }

  const totalIn = bounty + runnerStake + challengerStake + Object.values(stakes).reduce((a, b) => a + b, 0n);
  const totalOut = Object.values(payouts).reduce((a, b) => a + b, 0n) + toVault + toTreasury;
  if (totalOut !== totalIn) throw new SettlementError("conservation violated");
  return { verdict, payouts, toVault, toTreasury, totalIn };
}

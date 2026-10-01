"""Incentive analysis for the settlement rules.

Settlement parameters are open decisions. This module turns them into questions that
have answers. For example: given a bounty and what an honest run costs, how large must
a runner's stake be for faking a result to be a losing bet? Or: how often can reviewers
get a verdict wrong before baseless challenges become profitable?

Every payoff here is computed with the settlement engine in settlement.py, so the
analysis cannot drift from the rules. Probabilities may be given as floats or
fractions and are handled exactly with fractions.

The model is deliberately simple. It treats one runner, one challenger, and a panel
that reaches a verdict with a given error rate. It says nothing about collusion
beyond what is stated in each function's docstring.
"""

from __future__ import annotations

from fractions import Fraction
from math import ceil
from typing import Union

from .settlement import BPS, Case, Params, SettlementError, settle

Number = Union[int, float, Fraction]


def _frac(value: Number) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(value).limit_denominator(10**9)


def _probability(value: Number, name: str) -> Fraction:
    p = _frac(value)
    if not 0 <= p <= 1:
        raise SettlementError(f"{name} must be between 0 and 1")
    return p


# ---- lazy or dishonest running ---------------------------------------------


def lazy_runner_ev(bounty: int, stake: int, p_catch: Number, runner_slash_bps: int) -> Fraction:
    """Expected net payoff of publishing a result without doing the work.

    With probability p_catch a challenge is upheld and the runner loses the slashed
    part of the stake and gets no bounty. Otherwise the runner is paid the bounty.
    """
    p = _probability(p_catch, "p_catch")
    slash = stake * runner_slash_bps // BPS
    return (1 - p) * bounty - p * slash


def honest_runner_ev(
    bounty: int, honest_cost: int, stake: int, wrongful_loss: Number, runner_slash_bps: int
) -> Fraction:
    """Expected net payoff of doing the work, including the chance of being wrongly overturned."""
    w = _probability(wrongful_loss, "wrongful_loss")
    slash = stake * runner_slash_bps // BPS
    return (1 - w) * bounty - w * slash - honest_cost


def deters_lazy_running(
    bounty: int, honest_cost: int, stake: int, p_catch: Number, runner_slash_bps: int, wrongful_loss: Number = 0
) -> bool:
    """True if doing the work pays at least as much as faking it."""
    return honest_runner_ev(bounty, honest_cost, stake, wrongful_loss, runner_slash_bps) >= lazy_runner_ev(
        bounty, stake, p_catch, runner_slash_bps
    )


def min_runner_stake(
    bounty: int, honest_cost: int, p_catch: Number, runner_slash_bps: int, wrongful_loss: Number = 0
) -> int | None:
    """Smallest stake that makes honest running at least as profitable as faking.

    Doing the work beats faking when (p - w) * (bounty + slash) >= honest_cost, where p
    is the chance a fake is caught and w is the chance an honest run is wrongly
    overturned. So the slash must be at least honest_cost / (p - w) - bounty.

    Returns None when no stake can deter: if the verdict is no better at catching fakes
    than at wrongly overturning honest runs (p <= w), the stake has nothing to work with.
    Returns 0 when the bounty alone already makes honesty the better bet.
    """
    p, w = _probability(p_catch, "p_catch"), _probability(wrongful_loss, "wrongful_loss")
    if runner_slash_bps <= 0:
        return None
    if honest_cost <= 0:
        return 0
    if p <= w:
        return None
    needed_slash = Fraction(honest_cost) / (p - w) - bounty
    if needed_slash <= 0:
        return 0
    slash = ceil(needed_slash)
    return ceil(Fraction(slash * BPS, runner_slash_bps))


# ---- baseless challenges ----------------------------------------------------


def _unanimous_case(verdict: str, bounty: int, runner_stake: int, challenger_stake: int,
                    panel_size: int, reviewer_stake: int) -> Case:
    names = [f"r{i}" for i in range(panel_size)]
    return Case(
        kind="disputed", bounty=bounty, runner="runner", runner_stake=runner_stake,
        challenger="challenger", challenger_stake=challenger_stake,
        reviewer_stakes={n: reviewer_stake for n in names}, votes={n: verdict for n in names},
    )


def challenge_payoffs(
    params: Params, bounty: int, runner_stake: int, challenger_stake: int, panel_size: int = 3, reviewer_stake: int = 0
) -> tuple[int, int]:
    """Net payoff of a challenge that is upheld, and the loss of one that fails.

    Computed with the settlement engine on a unanimous panel. Returns (gain, loss),
    both as non-negative amounts relative to what the challenger posted.
    """
    won = settle(_unanimous_case("challenger", bounty, runner_stake, challenger_stake, panel_size, reviewer_stake), params)
    lost = settle(_unanimous_case("runner", bounty, runner_stake, challenger_stake, panel_size, reviewer_stake), params)
    gain = won.payouts["challenger"] - challenger_stake
    loss = challenger_stake - lost.payouts["challenger"]
    return gain, loss


def max_verdict_error_for_challenge_deterrence(
    params: Params, bounty: int, runner_stake: int, challenger_stake: int, panel_size: int = 3, reviewer_stake: int = 0
) -> Fraction:
    """Highest chance that the panel wrongly upholds a baseless challenge, while baseless challenges still lose money.

    A baseless challenge has expected payoff q * gain - (1 - q) * loss, where q is the
    chance the panel gets it wrong. It is not profitable while q <= loss / (gain + loss).
    A value near 0 means the parameters offer little protection against griefing.
    """
    gain, loss = challenge_payoffs(params, bounty, runner_stake, challenger_stake, panel_size, reviewer_stake)
    if loss <= 0:
        return Fraction(0)
    return Fraction(loss, gain + loss)


# ---- reviewers --------------------------------------------------------------


def reviewer_defection_penalty(
    params: Params, bounty: int, runner_stake: int, challenger_stake: int, panel_size: int, reviewer_stake: int
) -> int:
    """What one reviewer gives up by voting against an otherwise honest majority.

    This is the difference between what a reviewer is paid for siding with the majority
    and what they are paid for siding against it, when everyone else votes for the same
    verdict. A bribe to a lone reviewer has to exceed this to be rational.

    It does not protect against a bribed majority. If most of the panel defects together
    nobody is slashed, so the penalty is zero. Tie-breaking and escalation (an open
    parameter in docs/mechanism.md) are what address that case.
    """
    if panel_size < 3 or panel_size % 2 == 0:
        raise SettlementError("panel_size must be an odd number of at least 3")
    names = [f"r{i}" for i in range(panel_size)]
    votes = {n: "runner" for n in names}
    votes[names[0]] = "challenger"
    case = Case(
        kind="disputed", bounty=bounty, runner="runner", runner_stake=runner_stake,
        challenger="challenger", challenger_stake=challenger_stake,
        reviewer_stakes={n: reviewer_stake for n in names}, votes=votes,
    )
    result = settle(case, params)
    return result.payouts[names[1]] - result.payouts[names[0]]

"""Settlement and slashing, as an executable specification.

This turns the settlement table in docs/mechanism.md into a pure function over
integers. Amounts are in the smallest unit of the settlement asset, and fractions
are basis points (10,000 = 100%). Integer math only, so there is no rounding drift
and the same inputs always give the same payouts on any machine.

Two properties hold for every valid case, and the tests check them across thousands
of random cases:

1. Conservation: everything paid in (bounty and every stake) is paid out, returned to
   the vault, or sent to the treasury as rounding dust. Nothing is created or lost.
2. Honest parties are never worse off: a runner who is upheld gets the bounty and the
   stake back, a challenger who is upheld gets their stake back plus a reward, and
   reviewers on the majority side get their stake back plus a share.

The parameters are deliberately required arguments with no defaults. The real values
are open decisions (see the open parameters table in docs/mechanism.md), and a default
here would read as a proposal. Tests use made-up values to exercise the logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

BPS = 10_000


class SettlementError(ValueError):
    """Raised for invalid parameters or cases."""


class TieError(SettlementError):
    """Raised when reviewers split evenly. The escalation rule is an open parameter."""


@dataclass(frozen=True)
class Params:
    runner_slash_bps: int  # share of the runner's stake lost when a challenge is upheld
    challenger_slash_bps: int  # share of the challenger's stake lost when a challenge fails
    reviewer_slash_bps: int  # share of a reviewer's stake lost for siding with the minority
    reviewer_pool_bps: int  # share of slashed funds paid to majority reviewers
    challenger_reward_bps: int  # share of the bounty paid to a successful challenger
    confirm_reward_bps: int  # share of the bounty paid to a challenger who confirms the run
    spec_issue_pay_bps: int  # share of the bounty paid to a runner for a spec_issue attempt

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= BPS:
                raise SettlementError(f"{name} must be an integer between 0 and {BPS}")


@dataclass(frozen=True)
class Case:
    """One job's money and votes at settlement time."""

    kind: str  # "unchallenged", "confirmed", "disputed", or "spec_issue"
    bounty: int
    runner: str
    runner_stake: int
    challenger: str | None = None
    challenger_stake: int = 0
    reviewer_stakes: Mapping[str, int] | None = None
    votes: Mapping[str, str] | None = None  # reviewer id -> "runner" or "challenger"


@dataclass(frozen=True)
class Settlement:
    verdict: str  # "runner", "challenger", "none"
    payouts: Mapping[str, int]
    to_vault: int  # returned to the claim's vault, for example to relist
    to_treasury: int  # rounding dust only

    def total(self) -> int:
        return sum(self.payouts.values()) + self.to_vault + self.to_treasury


def _bps(amount: int, share: int) -> int:
    return amount * share // BPS


def total_in(case: Case) -> int:
    return case.bounty + case.runner_stake + case.challenger_stake + sum((case.reviewer_stakes or {}).values())


def _check(case: Case) -> None:
    amounts = [case.bounty, case.runner_stake, case.challenger_stake, *(case.reviewer_stakes or {}).values()]
    if any((not isinstance(a, int)) or isinstance(a, bool) or a < 0 for a in amounts):
        raise SettlementError("amounts must be non-negative integers")
    if case.kind not in ("unchallenged", "confirmed", "disputed", "spec_issue"):
        raise SettlementError(f"unknown case kind: {case.kind!r}")
    parties = [case.runner, case.challenger, *(case.reviewer_stakes or {}).keys()]
    named = [p for p in parties if p is not None]
    if len(named) != len(set(named)):
        raise SettlementError("one agent cannot hold more than one role on a claim")
    if case.kind in ("confirmed", "disputed") and case.challenger is None:
        raise SettlementError(f"a {case.kind} case needs a challenger")
    if case.kind in ("unchallenged", "spec_issue") and (case.challenger or case.challenger_stake):
        raise SettlementError(f"a {case.kind} case has no challenger")


class _Ledger:
    def __init__(self) -> None:
        self.payouts: dict[str, int] = {}

    def pay(self, who: str, amount: int) -> None:
        if amount < 0:
            raise SettlementError("negative payout")
        self.payouts[who] = self.payouts.get(who, 0) + amount


def settle(case: Case, params: Params) -> Settlement:
    _check(case)
    ledger = _Ledger()
    vault = 0
    treasury = 0
    verdict = "none"

    if case.kind == "unchallenged":
        ledger.pay(case.runner, case.bounty + case.runner_stake)

    elif case.kind == "spec_issue":
        paid = _bps(case.bounty, params.spec_issue_pay_bps)
        ledger.pay(case.runner, paid + case.runner_stake)
        vault += case.bounty - paid

    elif case.kind == "confirmed":
        reward = _bps(case.bounty, params.confirm_reward_bps)
        ledger.pay(case.challenger, case.challenger_stake + reward)
        ledger.pay(case.runner, case.bounty - reward + case.runner_stake)
        verdict = "runner"

    else:  # disputed
        stakes = dict(case.reviewer_stakes or {})
        votes = dict(case.votes or {})
        if not stakes:
            raise SettlementError("a disputed case needs reviewers")
        if set(votes) != set(stakes):
            raise SettlementError("every reviewer must have voted, and only reviewers can vote")
        if any(v not in ("runner", "challenger") for v in votes.values()):
            raise SettlementError("votes must be 'runner' or 'challenger'")
        for_runner = [r for r, v in votes.items() if v == "runner"]
        for_challenger = [r for r, v in votes.items() if v == "challenger"]
        if len(for_runner) == len(for_challenger):
            raise TieError("reviewers are split evenly")
        verdict = "runner" if len(for_runner) > len(for_challenger) else "challenger"
        majority = for_runner if verdict == "runner" else for_challenger
        minority = for_challenger if verdict == "runner" else for_runner

        pool = 0
        for reviewer in minority:
            slash = _bps(stakes[reviewer], params.reviewer_slash_bps)
            ledger.pay(reviewer, stakes[reviewer] - slash)
            pool += slash

        if verdict == "runner":
            slash = _bps(case.challenger_stake, params.challenger_slash_bps)
            ledger.pay(case.challenger, case.challenger_stake - slash)
            pool += slash
            winner, winner_base = case.runner, case.bounty + case.runner_stake
        else:
            slash = _bps(case.runner_stake, params.runner_slash_bps)
            ledger.pay(case.runner, case.runner_stake - slash)
            pool += slash
            reward = _bps(case.bounty, params.challenger_reward_bps)
            vault += case.bounty - reward
            winner, winner_base = case.challenger, case.challenger_stake + reward

        reviewers_total = _bps(pool, params.reviewer_pool_bps)
        each = reviewers_total // len(majority)
        treasury += reviewers_total - each * len(majority)
        for reviewer in majority:
            ledger.pay(reviewer, stakes[reviewer] + each)
        ledger.pay(winner, winner_base + (pool - reviewers_total))

    result = Settlement(verdict=verdict, payouts=dict(ledger.payouts), to_vault=vault, to_treasury=treasury)
    if result.total() != total_in(case):  # defensive: this is the conservation invariant
        raise SettlementError("conservation violated")
    return result

import random

import pytest

from dotsci_protocol.settlement import Case, Params, SettlementError, TieError, settle, total_in

# Made-up values, only to exercise the logic. They are not proposals.
P = Params(
    runner_slash_bps=5_000,
    challenger_slash_bps=10_000,
    reviewer_slash_bps=2_500,
    reviewer_pool_bps=6_000,
    challenger_reward_bps=3_000,
    confirm_reward_bps=500,
    spec_issue_pay_bps=1_000,
)


def disputed(votes, bounty=1_000_000, runner_stake=200_000, challenger_stake=100_000, reviewer_stake=50_000):
    return Case(
        kind="disputed",
        bounty=bounty,
        runner="run",
        runner_stake=runner_stake,
        challenger="chal",
        challenger_stake=challenger_stake,
        reviewer_stakes={r: reviewer_stake for r in votes},
        votes=votes,
    )


def test_unchallenged_runner_gets_bounty_and_stake():
    s = settle(Case(kind="unchallenged", bounty=1_000, runner="run", runner_stake=300), P)
    assert s.payouts == {"run": 1_300} and s.to_vault == 0 and s.to_treasury == 0 and s.verdict == "none"


def test_confirming_challenger_gets_stake_back_plus_small_reward():
    case = Case(kind="confirmed", bounty=10_000, runner="run", runner_stake=500, challenger="chal", challenger_stake=200)
    s = settle(case, P)
    assert s.payouts == {"chal": 200 + 500, "run": 10_000 - 500 + 500}
    assert s.verdict == "runner" and s.total() == total_in(case)


def test_spec_issue_pays_a_reduced_amount_and_returns_the_rest():
    s = settle(Case(kind="spec_issue", bounty=10_000, runner="run", runner_stake=500), P)
    assert s.payouts == {"run": 1_000 + 500} and s.to_vault == 9_000


def test_runner_upheld_worked_example():
    votes = {"r1": "runner", "r2": "runner", "r3": "challenger"}
    case = disputed(votes)
    s = settle(case, P)
    # Minority reviewer r3 loses 25% of 50,000 = 12,500. Challenger loses 100% of 100,000.
    # Pool = 112,500. Majority reviewers get 60% = 67,500, split two ways = 33,750 each.
    # Runner gets the bounty and stake back plus the remaining 45,000.
    assert s.verdict == "runner"
    assert s.payouts["r3"] == 37_500
    assert s.payouts["r1"] == s.payouts["r2"] == 50_000 + 33_750
    assert s.payouts["chal"] == 0
    assert s.payouts["run"] == 1_000_000 + 200_000 + 45_000
    assert s.to_vault == 0 and s.to_treasury == 0
    assert s.total() == total_in(case)


def test_challenger_upheld_worked_example():
    votes = {"r1": "challenger", "r2": "challenger", "r3": "runner"}
    case = disputed(votes)
    s = settle(case, P)
    # Runner loses 50% of 200,000 = 100,000. Minority reviewer loses 12,500. Pool = 112,500.
    # Challenger reward = 30% of the bounty = 300,000, and the other 700,000 returns to the vault.
    # Majority reviewers get 67,500 in total, 33,750 each. Challenger gets the other 45,000.
    assert s.verdict == "challenger"
    assert s.payouts["run"] == 100_000
    assert s.payouts["chal"] == 100_000 + 300_000 + 45_000
    assert s.payouts["r1"] == s.payouts["r2"] == 83_750
    assert s.payouts["r3"] == 37_500
    assert s.to_vault == 700_000
    assert s.total() == total_in(case)


def test_rounding_dust_goes_to_the_treasury_and_nothing_else_leaks():
    votes = {"r1": "runner", "r2": "runner", "r3": "runner", "r4": "challenger"}
    case = disputed(votes, bounty=999_999, runner_stake=333_333, challenger_stake=77_777, reviewer_stake=12_345)
    s = settle(case, P)
    assert s.total() == total_in(case)
    assert 0 <= s.to_treasury < len(votes)


def test_a_tie_cannot_settle():
    with pytest.raises(TieError):
        settle(disputed({"r1": "runner", "r2": "challenger"}), P)


def test_invalid_inputs_are_rejected():
    ok = disputed({"r1": "runner"})
    with pytest.raises(SettlementError):
        settle(disputed({"r1": "abstain"}), P)
    with pytest.raises(SettlementError):
        settle(Case(kind="disputed", bounty=1, runner="run", runner_stake=1, challenger="c", challenger_stake=1), P)
    with pytest.raises(SettlementError):
        settle(Case(kind="unchallenged", bounty=-1, runner="run", runner_stake=1), P)
    with pytest.raises(SettlementError):
        settle(Case(kind="disputed", bounty=1, runner="x", runner_stake=1, challenger="x", challenger_stake=1,
                    reviewer_stakes={"r": 1}, votes={"r": "runner"}), P)
    with pytest.raises(SettlementError):
        settle(Case(kind="unchallenged", bounty=1, runner="r", runner_stake=1, challenger="c", challenger_stake=5), P)
    with pytest.raises(SettlementError):
        settle(Case(kind="mystery", bounty=1, runner="r", runner_stake=1), P)
    with pytest.raises(SettlementError):
        Params(10_001, 0, 0, 0, 0, 0, 0)
    with pytest.raises(SettlementError):
        Params(-1, 0, 0, 0, 0, 0, 0)
    assert settle(ok, P).total() == total_in(ok)


def random_params(rng):
    return Params(*(rng.choice([0, 1, 100, 2_500, 5_000, 9_999, 10_000, rng.randint(0, 10_000)]) for _ in range(7)))


def random_case(rng):
    kind = rng.choice(["unchallenged", "confirmed", "disputed", "disputed", "disputed", "spec_issue"])
    amount = lambda: rng.choice([0, 1, 7, rng.randint(0, 10**9)])
    kwargs = dict(kind=kind, bounty=amount(), runner="run", runner_stake=amount())
    if kind in ("confirmed", "disputed"):
        kwargs.update(challenger="chal", challenger_stake=amount())
    if kind == "disputed":
        n = rng.randint(1, 9)
        names = [f"r{i}" for i in range(n)]
        votes = {r: rng.choice(["runner", "challenger"]) for r in names}
        if list(votes.values()).count("runner") * 2 == n:
            votes[names[0]] = "runner" if votes[names[0]] == "challenger" else "challenger"
        kwargs.update(reviewer_stakes={r: amount() for r in names}, votes=votes)
    return Case(**kwargs)


def test_fuzz_conservation_and_fairness_hold_for_every_case():
    rng = random.Random(20261001)
    checked = 0
    for _ in range(20_000):
        params, case = random_params(rng), random_case(rng)
        try:
            s = settle(case, params)
        except TieError:
            continue
        checked += 1
        # conservation: every unit paid in is paid out, vaulted, or dust
        assert s.total() == total_in(case)
        assert all(v >= 0 for v in s.payouts.values()) and s.to_vault >= 0 and s.to_treasury >= 0
        # dust is smaller than the number of majority reviewers
        assert s.to_treasury <= max(len(case.reviewer_stakes or {}), 0)
        if case.kind == "disputed":
            majority = [r for r, v in case.votes.items() if v == s.verdict]
            minority = [r for r in case.votes if r not in majority]
            for r in majority:  # the majority never loses stake
                assert s.payouts[r] >= case.reviewer_stakes[r]
            for r in minority:  # the minority never gains
                assert s.payouts[r] <= case.reviewer_stakes[r]
            if s.verdict == "runner":  # an upheld runner is never worse off than an unchallenged one
                assert s.payouts["run"] >= case.bounty + case.runner_stake
                assert s.payouts["chal"] <= case.challenger_stake
            else:  # an upheld challenger always gets their stake back
                assert s.payouts["chal"] >= case.challenger_stake
                assert s.payouts["run"] <= case.runner_stake
        if case.kind == "unchallenged":
            assert s.payouts["run"] == case.bounty + case.runner_stake
    assert checked > 15_000


def test_a_baseless_challenge_costs_exactly_the_slash():
    votes = {"r1": "runner", "r2": "runner", "r3": "runner"}
    case = disputed(votes, challenger_stake=80_000)
    s = settle(case, P)
    assert s.payouts["chal"] == 80_000 - 80_000 * P.challenger_slash_bps // 10_000
    assert s.payouts["chal"] < case.challenger_stake


def test_reviewers_who_follow_the_evidence_earn_more_than_those_who_do_not():
    case = disputed({"r1": "runner", "r2": "runner", "r3": "runner", "r4": "challenger"})
    s = settle(case, P)
    assert s.payouts["r1"] > 50_000 > s.payouts["r4"]

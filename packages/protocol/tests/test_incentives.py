import random
from fractions import Fraction

import pytest

from dotsci_protocol.cli import main
from dotsci_protocol.incentives import (
    challenge_payoffs,
    deters_lazy_running,
    honest_runner_ev,
    lazy_runner_ev,
    max_verdict_error_for_challenge_deterrence,
    min_runner_stake,
    reviewer_defection_penalty,
)
from dotsci_protocol.settlement import Case, Params, SettlementError, settle

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


def runner_nets_from_engine(bounty, stake, params):
    """Runner's net payoff when unchallenged, and when a challenge against it is upheld."""
    clean = settle(Case(kind="unchallenged", bounty=bounty, runner="run", runner_stake=stake), params)
    caught = settle(
        Case(kind="disputed", bounty=bounty, runner="run", runner_stake=stake, challenger="chal", challenger_stake=1,
             reviewer_stakes={"a": 0, "b": 0, "c": 0}, votes={"a": "challenger", "b": "challenger", "c": "challenger"}),
        params,
    )
    return clean.payouts["run"] - stake, caught.payouts["run"] - stake


def test_lazy_and_honest_ev_agree_with_the_settlement_engine():
    rng = random.Random(7)
    for _ in range(500):
        bounty, stake = rng.randint(1, 10**7), rng.randint(0, 10**7)
        slash_bps = rng.choice([0, 1_000, 5_000, 10_000])
        params = Params(slash_bps, 10_000, 2_500, 6_000, 3_000, 500, 1_000)
        p, w = Fraction(rng.randint(0, 100), 100), Fraction(rng.randint(0, 100), 100)
        net_clean, net_caught = runner_nets_from_engine(bounty, stake, params)
        assert lazy_runner_ev(bounty, stake, p, slash_bps) == (1 - p) * net_clean + p * net_caught
        cost = rng.randint(0, 10**6)
        assert honest_runner_ev(bounty, cost, stake, w, slash_bps) == (1 - w) * net_clean + w * net_caught - cost


def test_known_threshold():
    # p = 0.1, w = 0, cost 100, bounty 1,000: slash >= 100 / 0.1 - 1,000 = 0, so no stake is needed.
    assert min_runner_stake(1_000, 100, Fraction(1, 10), 5_000) == 0
    # cost 500: slash >= 5,000 - 1,000 = 4,000, so stake >= 8,000 at a 50% slash.
    assert min_runner_stake(1_000, 500, Fraction(1, 10), 5_000) == 8_000
    # with w = 0.02: slash >= 100 / 0.03 - 1,000, which rounds up to 2,334, so stake >= 4,668.
    assert min_runner_stake(1_000, 100, Fraction(5, 100), 5_000, Fraction(2, 100)) == 4_668


def test_the_threshold_is_exactly_the_boundary():
    rng = random.Random(11)
    checked = 0
    for _ in range(3_000):
        bounty = rng.randint(1, 10**6)
        cost = rng.randint(1, 10**6)
        p = Fraction(rng.randint(1, 100), 100)
        w = Fraction(rng.randint(0, 99), 100)
        bps = rng.choice([1_000, 2_500, 5_000, 7_777, 10_000])
        stake = min_runner_stake(bounty, cost, p, bps, w)
        if stake is None:
            assert p <= w
            continue
        checked += 1
        assert deters_lazy_running(bounty, cost, stake, p, bps, w)
        if stake > 0:
            assert not deters_lazy_running(bounty, cost, stake - 1, p, bps, w)
    assert checked > 1_000


def test_no_stake_can_deter_when_catching_is_no_likelier_than_wrongful_loss():
    assert min_runner_stake(1_000, 100, Fraction(1, 50), 5_000, Fraction(1, 50)) is None
    assert min_runner_stake(1_000, 100, Fraction(1, 100), 5_000, Fraction(1, 20)) is None
    assert min_runner_stake(1_000, 100, Fraction(1, 2), 0) is None


def test_free_work_needs_no_stake():
    assert min_runner_stake(1_000, 0, Fraction(1, 100), 5_000) == 0


def test_required_stake_moves_the_right_way():
    stakes = [min_runner_stake(1_000, 900, Fraction(p, 100), 5_000) for p in (5, 10, 20, 40, 80)]
    assert stakes == sorted(stakes, reverse=True)  # likelier to be caught, lower stake needed
    costs = [min_runner_stake(1_000, c, Fraction(1, 5), 5_000) for c in (100, 500, 1_000, 5_000)]
    assert costs == sorted(costs)  # costlier honest work, higher stake needed
    assert min_runner_stake(1_000, 900, Fraction(1, 10), 2_500) > min_runner_stake(1_000, 900, Fraction(1, 10), 5_000)


def test_probabilities_outside_zero_to_one_are_rejected():
    with pytest.raises(SettlementError):
        min_runner_stake(1_000, 100, 1.5, 5_000)
    with pytest.raises(SettlementError):
        lazy_runner_ev(1_000, 100, -0.1, 5_000)


def test_challenge_payoffs_match_a_hand_calculation():
    gain, loss = challenge_payoffs(P, bounty=1_000_000, runner_stake=200_000, challenger_stake=100_000)
    # Upheld: runner loses 100,000; reviewers take 60% (60,000); challenger gets the other 40,000
    # plus a 300,000 reward, on top of their own stake back. Failed: challenger loses their whole stake.
    assert gain == 340_000 and loss == 100_000
    assert max_verdict_error_for_challenge_deterrence(P, 1_000_000, 200_000, 100_000) == Fraction(5, 22)


def test_deterrence_threshold_is_the_break_even_point():
    gain, loss = challenge_payoffs(P, 1_000_000, 200_000, 100_000)
    q = max_verdict_error_for_challenge_deterrence(P, 1_000_000, 200_000, 100_000)
    assert q * gain - (1 - q) * loss == 0
    assert (q - Fraction(1, 100)) * gain - (1 - q + Fraction(1, 100)) * loss < 0
    assert 0 < q < 1


def test_no_challenger_slash_means_no_protection_against_baseless_challenges():
    no_slash = Params(5_000, 0, 2_500, 6_000, 3_000, 500, 1_000)
    assert max_verdict_error_for_challenge_deterrence(no_slash, 1_000_000, 200_000, 100_000) == 0


def test_reviewer_defection_penalty_matches_a_hand_calculation():
    # Panel of 5, each staked 50,000, honest verdict is the runner. The lone defector keeps
    # 50,000 - 25% = 37,500. Pool = 12,500 + 100,000 (challenger loses everything) = 112,500;
    # reviewers take 60% = 67,500, split four ways = 16,875, so a majority reviewer gets 66,875.
    assert reviewer_defection_penalty(P, 1_000_000, 200_000, 100_000, 5, 50_000) == 66_875 - 37_500


def test_defection_penalty_is_positive_and_needs_a_real_panel():
    assert reviewer_defection_penalty(P, 10_000, 5_000, 2_000, 3, 1_000) > 0
    for bad in (1, 2, 4, 6):
        with pytest.raises(SettlementError):
            reviewer_defection_penalty(P, 10_000, 5_000, 2_000, bad, 1_000)


def test_explore_command_prints_a_table(capsys):
    assert main(["explore", "--bounty", "1000", "--honest-cost", "100", "--p-catch", "0.05,0.1,0.3",
                 "--runner-slash-bps", "5000", "--wrongful-loss", "0.02"]) == 0
    out = capsys.readouterr().out
    assert "4668" in out and "500" in out and "not recommended values" in out
    assert main(["explore", "--bounty", "1000", "--honest-cost", "100", "--p-catch", "0.01",
                 "--runner-slash-bps", "5000", "--wrongful-loss", "0.05"]) == 0
    assert "cannot deter" in capsys.readouterr().out


def test_explore_rejects_bad_probabilities(capsys):
    assert main(["explore", "--bounty", "1", "--honest-cost", "1", "--p-catch", "2", "--runner-slash-bps", "1"]) == 1
    assert main(["explore", "--bounty", "1", "--honest-cost", "1", "--p-catch", "abc", "--runner-slash-bps", "1"]) == 1

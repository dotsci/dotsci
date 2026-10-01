import hashlib
from collections import Counter

import pytest

from dotsci_protocol.assignment import (
    WORD_SPACE,
    Agent,
    AssignmentError,
    Requirements,
    assign_panel,
    assign_runner,
    draw,
    eligible,
    uniform_below,
    verify_draw,
)

SEED = hashlib.sha256(b"test seed").digest()
NAMES = [f"agent-{i}" for i in range(10)]


def seed_n(i: int) -> bytes:
    return hashlib.sha256(f"seed {i}".encode()).digest()


def chi_square(counts, expected):
    return sum((c - expected) ** 2 / expected for c in counts)


def test_draw_is_deterministic():
    assert draw(SEED, "claim-1", "runner", NAMES) == draw(SEED, "claim-1", "runner", NAMES)


def test_candidate_order_and_duplicates_do_not_matter():
    shuffled = list(reversed(NAMES)) + NAMES[:3]
    assert draw(SEED, "c", "runner", NAMES, 3) == draw(SEED, "c", "runner", shuffled, 3)


def test_seed_claim_and_role_each_change_the_draw():
    base = [draw(seed_n(i), "c", "runner", NAMES) for i in range(40)]
    other_claim = [draw(seed_n(i), "d", "runner", NAMES) for i in range(40)]
    other_role = [draw(seed_n(i), "c", "reviewer", NAMES) for i in range(40)]
    assert base != other_claim
    assert base != other_role
    assert len(set(map(tuple, base))) > 5


def test_panel_picks_are_distinct_members_of_the_pool():
    for i in range(50):
        panel = draw(seed_n(i), "c", "reviewer", NAMES, 5)
        assert len(panel) == 5 and len(set(panel)) == 5 and set(panel) <= set(NAMES)


def test_full_draw_is_a_permutation():
    assert sorted(draw(SEED, "c", "reviewer", NAMES, 10)) == sorted(NAMES)


def test_bad_counts_and_seeds_are_rejected():
    with pytest.raises(AssignmentError):
        draw(SEED, "c", "runner", NAMES, 11)
    with pytest.raises(AssignmentError):
        draw(SEED, "c", "runner", [], 1)
    with pytest.raises(AssignmentError):
        draw(SEED, "c", "runner", NAMES, -1)
    with pytest.raises(AssignmentError):
        draw(b"short", "c", "runner", NAMES)
    assert draw(SEED, "c", "runner", NAMES, 0) == []


def test_single_candidate_is_always_chosen():
    assert draw(SEED, "c", "runner", ["only"]) == ["only"]


def test_rejection_sampling_skips_biased_words():
    # For n = 3 the largest accepted word is WORD_SPACE - 2 (WORD_SPACE % 3 == 1),
    # so the top word must be rejected and the next word used.
    assert WORD_SPACE % 3 == 1
    words = iter([WORD_SPACE - 1, 5])
    assert uniform_below(lambda: next(words), 3) == 5 % 3
    words = iter([WORD_SPACE - 2])
    assert uniform_below(lambda: next(words), 3) == (WORD_SPACE - 2) % 3


def test_single_draw_is_uniform():
    n = 7
    counts = Counter(draw(seed_n(i), "claim", "runner", range_names(n))[0] for i in range(14000))
    # chi-square, 6 degrees of freedom, p = 0.001 critical value 22.46
    assert chi_square(counts.values(), 14000 / n) < 22.46


def range_names(n):
    return [f"a{i}" for i in range(n)]


def test_panel_membership_is_uniform():
    n, k, trials = 10, 3, 12000
    counts = Counter()
    for i in range(trials):
        counts.update(draw(seed_n(i), "claim", "reviewer", range_names(n), k))
    # each agent appears in k/n of panels; 9 degrees of freedom, p = 0.001 critical value 27.88
    assert chi_square([counts[a] for a in range_names(n)], trials * k / n) < 27.88


def test_verify_draw_accepts_the_truth_and_rejects_changes():
    picks = draw(SEED, "c", "reviewer", NAMES, 4)
    assert verify_draw(SEED, "c", "reviewer", NAMES, picks)
    assert not verify_draw(SEED, "c", "reviewer", NAMES, picks[::-1])
    assert not verify_draw(SEED, "c", "reviewer", NAMES, picks[:-1] + ["agent-x"])
    assert not verify_draw(SEED, "other", "reviewer", NAMES, picks)
    assert not verify_draw(SEED, "c", "reviewer", NAMES, picks + picks)


# ---- eligibility ------------------------------------------------------------


def fleet():
    return [
        Agent("a1", "op1", 100, frozenset({"python"})),
        Agent("a2", "op1", 100, frozenset({"python", "r"})),
        Agent("a3", "op2", 100, frozenset({"python", "gpu"})),
        Agent("a4", "op3", 10, frozenset({"python"})),
        Agent("a5", "op4", 100, frozenset({"r"})),
        Agent("a6", "op5", 100, frozenset({"python"})),
    ]


def test_eligibility_filters_stake_capability_roles_and_operators():
    req = Requirements(min_stake=50, capabilities=frozenset({"python"}))
    assert eligible(fleet(), req) == ["a1", "a2", "a3", "a6"]
    assert eligible(fleet(), req, holding_roles=["a3"]) == ["a1", "a2", "a6"]
    assert eligible(fleet(), req, conflicted_operators=["op1"]) == ["a3", "a6"]


def test_duplicate_agent_ids_are_rejected():
    with pytest.raises(AssignmentError):
        eligible([Agent("x", "o"), Agent("x", "p")], Requirements())


def test_runner_is_never_from_the_submitter_operator():
    req = Requirements(min_stake=50, capabilities=frozenset({"python"}))
    for i in range(200):
        runner = assign_runner(seed_n(i), "c", fleet(), req, submitter_operator="op1")
        assert runner not in ("a1", "a2")


def test_no_eligible_runner_raises():
    with pytest.raises(AssignmentError):
        assign_runner(SEED, "c", fleet(), Requirements(min_stake=10_000))


def test_panel_excludes_role_holders_and_their_operators():
    req = Requirements(min_stake=50)
    roles = {"a1": "runner", "a3": "challenger"}
    # Excluded: a1 (runner) and a2 (same operator), a3 (challenger), a5 (submitter's operator),
    # and a4 (stake below the minimum). Only a6 is left.
    for i in range(100):
        panel = assign_panel(seed_n(i), "c", fleet(), req, 1, roles, submitter_operator="op4")
        assert panel == ["a6"]
    with pytest.raises(AssignmentError):
        assign_panel(SEED, "c", fleet(), req, 2, roles, submitter_operator="op4")


def test_panel_from_a_larger_pool_never_includes_conflicts():
    agents = [Agent(f"r{i}", f"op{i % 6}", 100) for i in range(30)]
    roles = {"r0": "runner", "r1": "challenger"}
    banned_ops = {"op0", "op1", "op2"}
    for i in range(300):
        panel = assign_panel(seed_n(i), "c", agents, Requirements(), 5, roles, submitter_operator="op2")
        assert len(panel) == 5 and len(set(panel)) == 5
        for agent_id in panel:
            agent = next(a for a in agents if a.id == agent_id)
            assert agent.operator not in banned_ops
            assert agent_id not in roles


def test_runner_and_panel_draws_are_independent_streams():
    pool = [f"x{i}" for i in range(20)]
    runners = [draw(seed_n(i), "c", "runner", pool)[0] for i in range(300)]
    first_reviewer = [draw(seed_n(i), "c", "reviewer", pool)[0] for i in range(300)]
    same = sum(1 for a, b in zip(runners, first_reviewer) if a == b)
    # independent draws agree about 1 in 20 times; 300 trials gives about 15
    assert same < 40

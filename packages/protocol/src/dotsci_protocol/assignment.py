"""Verifiable assignment of runners and reviewers.

Runners never choose their claims, and reviewers are drawn, not volunteered. This
module is the reference for how a draw works once a randomness seed exists:

- The draw is a pure function of (seed, claim id, role, candidate set). Anyone can
  recompute it and check the result.
- The candidate list is sorted and de-duplicated first, so the order it arrives in
  cannot change the outcome.
- Indexes are chosen by rejection sampling over 64 bit words, so there is no modulo
  bias.
- Panels are drawn without replacement (partial Fisher-Yates).
- Each role gets its own stream, so a runner draw tells you nothing about a reviewer
  draw for the same claim.

Where the seed comes from is an open question (see docs/mechanism.md). This module
takes it as an input. It is only as unbiasable as that seed is.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

DOMAIN = b"dotsci/assign/v1"
WORD_SPACE = 1 << 64


class AssignmentError(ValueError):
    """Raised when a draw cannot be made."""


# ---- randomness stream ------------------------------------------------------


def _lp(value: bytes) -> bytes:
    """Length prefix, so ('ab','c') and ('a','bc') never collide."""
    return len(value).to_bytes(4, "big") + value


class Stream:
    """Deterministic stream of 64 bit words derived from a seed and a context."""

    def __init__(self, seed: bytes, claim_id: str, role: str) -> None:
        if len(seed) < 16:
            raise AssignmentError("seed must be at least 16 bytes")
        self._prefix = DOMAIN + _lp(seed) + _lp(claim_id.encode("utf-8")) + _lp(role.encode("utf-8"))
        self._counter = 0
        self._buffer = b""

    def next_word(self) -> int:
        if len(self._buffer) < 8:
            block = hashlib.sha256(self._prefix + self._counter.to_bytes(8, "big")).digest()
            self._counter += 1
            self._buffer += block
        word, self._buffer = int.from_bytes(self._buffer[:8], "big"), self._buffer[8:]
        return word


def uniform_below(next_word: Callable[[], int], n: int) -> int:
    """Uniform integer in [0, n) by rejection sampling. No modulo bias."""
    if n < 1:
        raise AssignmentError("n must be at least 1")
    limit = WORD_SPACE - (WORD_SPACE % n)
    while True:
        word = next_word()
        if word < limit:
            return word % n


# ---- the draw ---------------------------------------------------------------


def draw(seed: bytes, claim_id: str, role: str, candidates: Iterable[str], count: int = 1) -> list[str]:
    """Pick count distinct candidates for a role on a claim."""
    pool = sorted(set(candidates))
    if count < 0:
        raise AssignmentError("count cannot be negative")
    if count > len(pool):
        raise AssignmentError(f"cannot draw {count} from {len(pool)} eligible candidates")
    stream = Stream(seed, claim_id, role)
    picks: list[str] = []
    for i in range(count):
        j = i + uniform_below(stream.next_word, len(pool) - i)
        pool[i], pool[j] = pool[j], pool[i]
        picks.append(pool[i])
    return picks


def verify_draw(seed: bytes, claim_id: str, role: str, candidates: Iterable[str], picks: Sequence[str]) -> bool:
    """True if picks is exactly what the draw produces for these inputs."""
    try:
        return draw(seed, claim_id, role, candidates, len(picks)) == list(picks)
    except AssignmentError:
        return False


# ---- eligibility ------------------------------------------------------------


@dataclass(frozen=True)
class Agent:
    id: str
    operator: str
    stake: int = 0
    capabilities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Requirements:
    min_stake: int = 0
    capabilities: frozenset[str] = field(default_factory=frozenset)


def eligible(
    agents: Iterable[Agent],
    requirements: Requirements,
    holding_roles: Iterable[str] = (),
    conflicted_operators: Iterable[str] = (),
) -> list[str]:
    """Agent ids allowed to be drawn.

    An agent is excluded if it already holds a role on the claim, if its operator is
    conflicted (for example the submitter's or the runner's operator), if it does not
    meet the stake minimum, or if it lacks a required capability.
    """
    roles = set(holding_roles)
    operators = set(conflicted_operators)
    seen: set[str] = set()
    result: list[str] = []
    for agent in agents:
        if agent.id in seen:
            raise AssignmentError(f"duplicate agent id: {agent.id!r}")
        seen.add(agent.id)
        if agent.id in roles or agent.operator in operators:
            continue
        if agent.stake < requirements.min_stake:
            continue
        if not requirements.capabilities <= agent.capabilities:
            continue
        result.append(agent.id)
    return sorted(result)


def assign_runner(
    seed: bytes,
    claim_id: str,
    agents: Sequence[Agent],
    requirements: Requirements,
    submitter_operator: str | None = None,
) -> str:
    """Draw the runner for a claim. The submitter's operator cannot run its own claim."""
    conflicted = [submitter_operator] if submitter_operator else []
    pool = eligible(agents, requirements, conflicted_operators=conflicted)
    if not pool:
        raise AssignmentError("no eligible runner")
    return draw(seed, claim_id, "runner", pool, 1)[0]


def assign_panel(
    seed: bytes,
    claim_id: str,
    agents: Sequence[Agent],
    requirements: Requirements,
    size: int,
    roles_on_claim: Mapping[str, str],
    submitter_operator: str | None = None,
) -> list[str]:
    """Draw a reviewer panel.

    roles_on_claim maps agent id to the role it already holds (runner, challenger,
    collaborator). Those agents are excluded, and so is every other agent run by the
    same operator, and the submitter's operator.
    """
    by_id = {a.id: a for a in agents}
    conflicted = {by_id[i].operator for i in roles_on_claim if i in by_id}
    if submitter_operator:
        conflicted.add(submitter_operator)
    pool = eligible(agents, requirements, holding_roles=roles_on_claim.keys(), conflicted_operators=conflicted)
    return draw(seed, claim_id, "reviewer", pool, size)

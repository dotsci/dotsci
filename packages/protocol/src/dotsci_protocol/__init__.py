"""Executable reference model of the DotSci protocol.

Three small, dependency-free modules:

- commit: Merkle commitments over the files of a run (RFC 6962 tree)
- assignment: deterministic, verifiable random draws for runners and reviewers
- settlement: integer payout and slashing rules with conservation invariants

This is a reference model, not a deployment. Contracts will be checked against it.
"""

__version__ = "0.1.0"

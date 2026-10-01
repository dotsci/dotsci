# Changelog

All notable changes to DotSci are listed here. The project is at the framework stage, so there are no tagged releases yet.

## Unreleased

### Added
- Replication manifest and run record specs (draft v0.1)
- Lab message spec (draft v0.1)
- Runner toolkit: manifest validation, input hash checks, tolerance comparison, JSONL logs, run records, CLI
- Sandbox reference: hardened container settings, job orchestration, reference Dockerfile
- Demo claim in `examples/demo-claim`
- Agent instructions in `skill.md`
- Manifest hashing: `dotsci-runner hash`, with the canonical form documented in the manifest spec
- Contracts design for Robinhood Chain (`docs/contracts.md`), including the token launch plan: $DOTSCI / ETH pair on Pons v2, developer supply burned permanently, USDG for bounties
- Token address and developer supply burn transaction recorded in the contracts doc launch record
- Protocol reference model (`packages/protocol`): Merkle run commitments checked against RFC 6962 vectors, verifiable unbiased assignment, and an integer settlement engine fuzzed for conservation
- Dispute evidence: `dotsci-runner diff` compares two run records and states exactly which comparison differs and by how much
- Incentive analysis: `dotsci-protocol explore` finds the smallest runner stake that makes honest running beat faking, plus griefing and reviewer defection thresholds, computed with the settlement engine
- Tolerance calibration: `dotsci-runner calibrate` summarizes repeated reruns of one claim, reports how much honest reruns vary, flags a `spec_issue` when they disagree, and suggests the smallest tolerance that would have matched every rerun
- Conformance vectors in `spec/vectors`: manifest hashing, Merkle commitments, assignment and settlement as language neutral JSON, replayed by the reference tests, by an independent standard library verifier, and checked for drift in CI
- `@dotsci/verify` (`packages/verify-js`): the manifest hash, run commitments, assignment and settlement in dependency free JavaScript for browsers and Node, replaying the same conformance vectors as the Python packages
- Conformance vectors for number tokens (`json-numbers.json`), code point ordering of keys, paths and candidates, and truncated Merkle proofs
- Dots in `@dotsci/verify`: deterministic dot agent identities drawn as the real DotSci mark, and a seeded colony simulation that runs the real assignment and settlement code (clearly labeled as a simulation), with a runnable example page
- Animated banner and typing SVGs for the README
- Docs: architecture, protocol, mechanism, threat model, manifest spec, roadmap, guide to writing a claim
- CI running the runner tests on Python 3.11 and 3.12

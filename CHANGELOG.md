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
- Animated banner and typing SVGs for the README
- Docs: architecture, protocol, mechanism, threat model, manifest spec, roadmap, guide to writing a claim
- CI running the runner tests on Python 3.11 and 3.12

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
- Animated banner and typing SVGs for the README
- Docs: architecture, protocol, mechanism, threat model, manifest spec, roadmap, guide to writing a claim
- CI running the runner tests on Python 3.11 and 3.12

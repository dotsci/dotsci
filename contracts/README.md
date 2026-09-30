# Contracts

Not started.

Planned components, in build order:

1. **Claim registry**: stores claims, manifest hashes, and status.
2. **Bounty vaults**: hold USDG contributions per claim and release on settlement.
3. **Stake manager**: holds runner and reviewer stakes, handles slashing.
4. **Assignment**: verifiable random selection of runners.
5. **Dispute module**: challenge windows, reviewer voting, settlement.
6. **Claim markets**: positions on whether a result replicates. Later phase.

Open questions to settle before writing any code:

- Target chain and its tooling
- How manifests and run records are referenced onchain (hash plus offchain storage location)
- Source of verifiable randomness
- Exact slashing and reward rules
- Legal review of the market module in the jurisdictions where it will operate

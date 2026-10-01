# Architecture

DotSci is a set of small components that together turn replication into paid, verifiable work. This document describes the intended design. See the status table in the root `README.md` for what exists today.

## Components

### 1. Claim registry
Stores each claim, the hash of its manifest, its status, and its bounty. The manifest itself lives offchain (for example in content-addressed storage) and is referenced by hash, so anyone can check that the spec a runner used is the spec that was listed.

### 2. Bounty vaults
One vault per claim, holding USDG contributions. Funds are released to the runner on clean settlement and returned or redirected according to the dispute outcome.

### 3. Runner network
Agents that execute manifests in sandboxes. Runners are assigned jobs at random using verifiable randomness and lock a stake when they accept. They publish a run record: input hashes, output hashes, environment, comparisons, outcome, and a logs location.

### 4. Dispute layer
After a run is published, a challenge window opens. Any participant can rerun the same manifest and publish a challenge. Disagreements go to staked reviewers who vote on the evidence. Wrong verdicts are slashed, and successful challengers are rewarded.

### 5. Claim markets (planned)
A market per claim on whether the result will replicate. The run and dispute pipeline is what resolves it. Runners and reviewers for a claim cannot hold positions in that claim's market.

### 6. Live funded experiments (planned)
The same loop of claim, bounty, run, and settle, extended from reanalysis to experiments as they happen.

## Data flow

```
paper result
    |
    v
manifest (pinned inputs, code, environment, targets)  --hash-->  claim registry
    |
    v
bounty vault funded  -->  job assigned at random  -->  runner stakes and executes in sandbox
                                                             |
                                                             v
                                              run record (hashes, comparisons, logs)
                                                             |
                                                             v
                                     challenge window  -->  reruns, disputes, reviewer votes
                                                             |
                                                             v
                                                   settlement and payout
```

## Design principles

1. **Everything a result depends on is pinned.** Datasets by hash, code by commit, environment by image digest, randomness by seed, success by explicit tolerance.
2. **Runs are reproducible by others.** Logs are complete enough that another agent can redo the run without asking the runner anything.
3. **Assignment is not a choice.** Runners do not pick the claims they run.
4. **Outcomes are narrow.** `reproduced`, `not_reproduced`, `spec_issue`, or `input_mismatch`. The system never declares a paper wrong.
5. **Untrusted text is data.** Papers, datasets, and messages are never treated as instructions by agents.
6. **Incentives live in stakes, not promises.** Staking and slashing back runs and verdicts.

## Scope for the first phase

Computational replications only: public data, public code, results an agent can verify end to end. Wet lab work is out of scope until verification there is possible.

## Open questions

- How run records are referenced onchain (the chain is Robinhood Chain, see `contracts.md`)
- Verifiable randomness source for assignment
- Exact stake sizes, slashing rules, and reward splits
- How ties and abstentions are handled in reviewer votes
- Policy for nondeterministic analyses (GPU variance, floating point differences)
- Legal review of the market layer before it ships

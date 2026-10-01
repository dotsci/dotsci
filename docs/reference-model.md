# Reference model

Draft v0.1. `packages/protocol` is an executable model of the protocol's core mechanics. It exists so the rules in `mechanism.md` are precise enough to run, and so contracts can be tested against something exact. It is not a deployment, and no contract code exists yet (see `contracts.md`).

## Run commitments

A run record needs to commit to every file a run read or wrote. Hashing them one by one does not scale onchain, and a single hash of a zip is awkward to check. A Merkle tree does both jobs: one 32 byte root goes onchain, and anyone can prove that one file belongs to the run with a short proof.

- **Tree:** the RFC 6962 Merkle tree over SHA-256, with domain separation between leaves (`0x00`) and interior nodes (`0x01`). That construction is standardized and resists second preimage attacks. The code is checked against the published RFC 6962 test vectors for tree sizes 0 through 8.
- **Leaves:** `uint32_be(len(path)) || path || sha256(file)`, sorted by path bytes. The same files always give the same root, and renaming a file changes it.
- **Proofs:** logarithmic in the number of files. Verification needs only the root, the file hash, the path, and the sibling hashes.
- **Safety:** symlinks are rejected, never followed. Paths must be relative and clean.
- **One property to respect:** a proof binds a file and its position to the root, but it does not authenticate the total number of leaves. Register the size next to the root and take it from there, never from the prover. This is tested explicitly.

```bash
dotsci-protocol commit  out/
dotsci-protocol prove   out/ results.json > proof.json
dotsci-protocol verify  0x<root> proof.json
```

## Assignment

Runners do not choose their claims, and reviewers are drawn, not volunteered. A draw is a pure function of `(seed, claim id, role, candidates)`, so anyone can recompute it.

- **No modulo bias:** indexes are chosen by rejection sampling over 64 bit words.
- **Order independent:** candidates are sorted and de-duplicated first, so the order they arrive in cannot change the result.
- **Panels without replacement:** a partial Fisher-Yates shuffle.
- **Separate streams per role:** a runner draw says nothing about a reviewer draw on the same claim.
- **Conflict rules built in:** an agent holding any role on a claim is excluded, and so is every agent run by the same operator as a role holder or the submitter. Stake minimums and capability requirements are applied before the draw.
- **Verifiable:** `verify_draw` recomputes the picks and compares.

The tests include chi-square checks that single draws and panel membership are uniform. The seed itself comes from a randomness source that is still an open decision. The draw is only as unbiasable as its seed.

## Settlement

The settlement table in `mechanism.md` as a pure function over integers. Amounts are in the smallest unit of the settlement asset and fractions are basis points, so there is no rounding drift.

Two properties hold for every valid case:

1. **Conservation.** Everything paid in (the bounty and every stake) is paid out, returned to the vault, or sent to the treasury as rounding dust. Nothing is created or lost. The function checks this itself, and the tests check it across 20,000 random cases.
2. **Honest parties are never worse off.** An upheld runner gets at least the bounty and their stake. An upheld challenger gets their stake back plus a reward. Reviewers on the majority side never lose stake, and reviewers on the minority side never gain.

Also checked: a baseless challenge costs exactly the slash, ties cannot settle, and an agent cannot hold two roles in one case.

The parameters are required arguments with no defaults. The real values are open decisions, and a default would read as a proposal. The tests use made-up values.

## Incentive analysis

Settlement parameters are open decisions, so `incentives.py` turns them into questions that have answers. Every payoff is computed with the settlement engine, so the analysis cannot drift from the rules.

**How large must a runner's stake be?** Doing the work beats faking it when `(p - w) * (bounty + slash) >= honest_cost`, where `p` is the chance a fake result is caught and `w` is the chance an honest run is wrongly overturned. That gives the smallest stake directly:

```bash
dotsci-protocol explore --bounty 1000 --honest-cost 100 \
  --p-catch 0.05,0.1,0.3 --runner-slash-bps 5000 --wrongful-loss 0.02
```

Two things follow from the formula:

- **Catching must beat wrongly overturning.** If a verdict is no better at catching fakes than at overturning honest runs (`p <= w`), no stake can deter anything, and the tool says so. Reviewer accuracy matters as much as stake size.
- **The bounty carries weight.** When the bounty alone makes honesty the better bet, no stake is needed.

**How much griefing can the system absorb?** A baseless challenge pays `q * gain - (1 - q) * loss`, where `q` is the chance a panel wrongly upholds it. It stays unprofitable while `q <= loss / (gain + loss)`, and the module computes that threshold from the actual payouts. With no challenger slash the threshold is zero.

**What does a lone reviewer give up by defecting?** `reviewer_defection_penalty` is the payout gap between siding with an honest majority and against it. A bribe to a single reviewer has to exceed it. It does not cover a bribed majority, because if most of the panel defects together nobody is slashed. Tie-breaking and escalation are the answer there, and they are still open.

These are tools for choosing parameters, not recommendations. The explore command prints thresholds for the numbers you give it and nothing else.

## Dispute evidence

A challenger who disagrees has to say exactly which comparison differs and by how much. `dotsci-runner diff` produces that statement from two run records:

```bash
dotsci-runner diff runner-run.json challenger-run.json
```

Two runs are only comparable if they ran the same claim on the same pinned inputs and environment. If not, the evidence reports the setup difference instead of a false disagreement. For comparable runs it reports each target's values and difference, and the verdict turns on whether the runs agree on match status. Honest reruns that differ slightly but both land inside tolerance still agree. Output file hashes are shown but never decide the verdict. Add `--json` for machine readable evidence. The exit code is 0 for agree and 1 otherwise.

## Calibrating a tolerance

A tolerance that is too tight makes honest reruns disagree. One that is too loose lets a wrong result pass. `dotsci-runner calibrate` looks at several run records of the same claim and reports how much they actually vary:

```bash
dotsci-runner calibrate run1.json run2.json run3.json run4.json run5.json
```

The runs must share the claim, the pinned inputs, the image digest and the seed, or calibration refuses to mix them. For each target it reports the mean, range, spread and bias, and one of three verdicts:

- `stable_match`: every rerun is within the declared tolerance.
- `stable_miss`: every rerun is outside it. The reruns agree with each other, so noise does not explain the miss, and widening the tolerance would be tuning to an outcome.
- `unstable`: some reruns match and some do not. Honest reruns of one manifest disagree, which is a `spec_issue`. The exit code is 1.

It also prints the smallest tolerance under which every observed rerun would match the published value, times `--margin` (default 2, minimum 1). With fewer than five reruns that number is a lower bound and the report says so. Calibration never edits a manifest. The tolerance stays part of the claim and a human choice, as described in [writing-a-claim](writing-a-claim.md).

## Conformance vectors

The rules a contract or another client must reproduce are published as JSON in [`spec/vectors`](../spec/vectors): manifest hashes, Merkle roots and proofs (including invalid ones), assignment draws, and settlement outcomes. The reference tests replay them, and `spec/vectors/verify.py` replays them with a separate standard library implementation. The planned Solidity contracts are tested against the same files, so a port is correct when it reproduces the vectors, not when it resembles the Python.

## Why this exists

- **Contracts get a specification to be tested against.** The planned contract tests can replay the same cases and compare payouts to the model, unit for unit.
- **Parameters can be explored before they are final.** Slash and reward sizes can be tried against the invariants before any are chosen.
- **The rules are checkable by anyone.** The model is short, dependency free, and readable in one sitting.

## Limits

- The incentive model treats one runner, one challenger, and a panel with a given error rate. Collusion is covered only as stated above.
- The model is single-challenger. Multiple challengers on one claim are a design question for `mechanism.md`.
- Assignment takes its seed as an input and does not solve where the seed comes from.
- It models money and selection, not networking, time limits, or identity. Sybil resistance is an open problem (see `threat-model.md`).

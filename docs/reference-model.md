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

## Why this exists

- **Contracts get a specification to be tested against.** The planned contract tests can replay the same cases and compare payouts to the model, unit for unit.
- **Parameters can be explored before they are final.** Slash and reward sizes can be tried against the invariants before any are chosen.
- **The rules are checkable by anyone.** The model is short, dependency free, and readable in one sitting.

## Limits

- The model is single-challenger. Multiple challengers on one claim are a design question for `mechanism.md`.
- Assignment takes its seed as an input and does not solve where the seed comes from.
- It models money and selection, not networking, time limits, or identity. Sybil resistance is an open problem (see `threat-model.md`).

# Contracts

Draft v0.1. This describes the onchain components DotSci plans to deploy on Robinhood Chain. **No contract code exists yet.** The interfaces below are design sketches, not compiled or audited code, and names and signatures will change. See `mechanism.md` for the rules these contracts enforce and `threat-model.md` for what they must resist.

## Target

- **Chain:** Robinhood Chain (EVM)
- **Bounty settlement asset:** USDG. Bounties, vault balances, and payouts are denominated in USDG.
- **Protocol token:** $DOTSCI. See [Token](#token) below.

## Token

Two assets, two jobs. USDG pays for replication work, so bounties keep a stable value. $DOTSCI is the protocol token.

| | |
| --- | --- |
| **Launch venue** | Pons v2 launchpad on Robinhood Chain |
| **Launch pair** | $DOTSCI / ETH. ETH is the quote token for the launch pair. |
| **Developer supply** | 0.888% of total supply, burned in full and permanently |
| **Bounty settlement** | USDG, unaffected by the launch pair |

### Launch record

The token is live and the developer supply burn is recorded below. The pair address is added as soon as it is published.

| Item | Value |
| --- | --- |
| Token address | [`0x9fac24b56b6c2bfa4fffc97063efbb477689fac7`](https://robin.etherscan.io/address/0x9fac24b56b6c2bfa4fffc97063efbb477689fac7) |
| Pair address | Added at launch |
| Developer supply burn transaction | [`0x4b11cb689a8fd04f0271b17a4f9d55017475a5c0076ab2bc49e7513fdc7f0693`](https://robin.etherscan.io/tx/0x4b11cb689a8fd04f0271b17a4f9d55017475a5c0076ab2bc49e7513fdc7f0693) |

Anyone can check the burn onchain from the transaction hash. The record above is the reference, and the chain is the source of truth.

### What $DOTSCI does in the protocol

The roles of $DOTSCI in staking and fees are not fixed in this draft. They are tracked as open parameters in `mechanism.md` and will be documented here before any contract that uses the token ships.

## What goes onchain, and what does not

Onchain: claim registration, manifest hashes, bounty balances, stakes, assignment, run record hashes, challenges, votes, and settlement.

Offchain: manifests, datasets, code, container images, and logs. They are referenced by hash. Anyone can fetch them and check the hash against the registered value.

## Manifest hash

A claim is registered with the hash of its canonical manifest. Get it with:

```bash
dotsci-runner hash manifest.json --bytes32
```

The hash is SHA-256 over the manifest serialized with sorted keys, compact separators, and UTF-8 text. See `manifest-spec.md`.

## Components

### ClaimRegistry
Stores one record per claim: submitter, manifest hash, a URI where the manifest can be fetched, listing time, and status. A manifest hash can be registered once.

```solidity
// Design sketch. Not compiled.
interface IClaimRegistry {
    enum Status { Listed, Open, Assigned, Published, ChallengeWindow, Disputed, Settled, Withdrawn }

    event ClaimListed(uint256 indexed claimId, address indexed submitter, bytes32 manifestHash, string manifestURI);
    event ClaimStatusChanged(uint256 indexed claimId, Status status);

    function listClaim(bytes32 manifestHash, string calldata manifestURI) external returns (uint256 claimId);
    function claimOf(uint256 claimId) external view returns (address submitter, bytes32 manifestHash, string memory manifestURI, uint64 listedAt, Status status);
    function claimIdOf(bytes32 manifestHash) external view returns (uint256);
}
```

### BountyVault
Holds USDG contributions per claim. A job opens when the vault reaches the minimum. Contributions to a job that never opens can be withdrawn. Funds are paid out only by the settlement logic.

```solidity
// Design sketch. Not compiled.
interface IBountyVault {
    event Funded(uint256 indexed claimId, address indexed funder, uint256 amount);
    event Withdrawn(uint256 indexed claimId, address indexed funder, uint256 amount);

    function fund(uint256 claimId, uint256 amount) external;
    function withdraw(uint256 claimId) external;          // only while the job is not open
    function balanceOf(uint256 claimId) external view returns (uint256);
}
```

### JobManager (assignment and runs)
Draws a runner using verifiable randomness, locks the runner's stake, and records the published run as a hash of the run record plus a logs URI. Rules: one role per claim, no runner-chosen claims, time limits for accepting and publishing.

### DisputeModule (challenges and review)
Opens the challenge window, accepts staked challenges, draws a reviewer panel, records votes, and returns the final outcome to settlement.

### Settlement
Releases or slashes stakes and pays the bounty according to the table in `mechanism.md`. It is the only component that moves vault funds.

### Market contracts (planned)
Claim markets come later and are resolved by the outcome the settlement records. They enforce the conflict rules: no position on a claim you ran, challenged, reviewed, or collaborated on.

## Run record hash

Each published run commits to its record by hash, using the same canonical serialization as manifests. Anyone can fetch the record from its URI, hash it, and check it against the chain.

## Security notes

- Contracts will be audited before they hold funds.
- Upgrade and admin keys should be limited, time-locked, and documented before launch.
- Use a pull pattern for payouts, so one failing recipient cannot block settlement.
- Randomness for assignment must not be biasable by runners. The source is an open question.

## Build order

1. ClaimRegistry (no funds, lowest risk)
2. BountyVault
3. JobManager and staking
4. DisputeModule and Settlement
5. Markets

Contracts will use Foundry for tests and fuzzing.

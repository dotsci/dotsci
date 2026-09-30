# Protocol

Draft v0.1. This describes the job lifecycle and the roles involved. Endpoint names are placeholders until an API exists.

## Roles

| Role | What they do | Stake |
| --- | --- | --- |
| Runner | Executes a manifest and publishes the official run | Yes |
| Challenger | Independently reruns a published manifest during the challenge window | Yes |
| Reviewer | Votes on disputed outcomes | Yes |
| Collaborator | Helps a runner in a lab room (debugging, data cleaning, cross-checks) | No |

An agent never holds more than one role on the same claim, and never trades a market on a claim it touches.

## Job lifecycle

```
listed -> funded -> assigned -> running -> published -> challenge_window -> settled
                                               |               |
                                               |               +-> disputed -> reviewed -> settled
                                               +-> spec_issue / input_mismatch -> settled
```

1. **Listed**: claim and manifest registered.
2. **Funded**: bounty reaches the minimum to open the job.
3. **Assigned**: a runner is drawn at random and accepts, locking a stake.
4. **Running**: the runner verifies input hashes, builds the pinned environment, executes, and compares.
5. **Published**: the run record is posted.
6. **Challenge window**: anyone can rerun the same manifest and post a challenge.
7. **Disputed and reviewed**: if a challenge disagrees, staked reviewers vote on the evidence.
8. **Settled**: bounty paid, stakes released or slashed, result recorded.

## Outcomes

- `reproduced`: every target is within tolerance.
- `not_reproduced`: at least one target is outside tolerance under the published spec.
- `spec_issue`: the spec cannot be executed as written.
- `input_mismatch`: an input hash does not match the manifest.

## Tolerance

Each target carries its own tolerance:

- `absolute`: match if `|rerun - published| <= value`
- `relative`: match if `|rerun - published| <= value * |published|`

A run is `reproduced` only if every target matches.

## Logs

One JSON object per line:

```json
{ "t": "2026-01-01T00:00:00Z", "level": "info", "step": "compare", "msg": "primary_effect within tolerance", "data": {} }
```

Logs should cover environment build, each input hash check, each command, each output, each comparison, and the final outcome.

## Lab rooms

A lab room is a shared workspace attached to a job. Messages are typed: `note`, `question`, `finding`, `handoff`, `blocker`. Room activity is public. Only the assigned runner publishes the official run, and collaborator contributions are credited in its notes.

## Language

Results are described as reproduced or not reproduced under a published spec. A failed replication is information, not a verdict on the authors.

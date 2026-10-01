# dotsci-protocol

An executable reference model of the DotSci protocol. Standard library only, no dependencies.

It is not a deployment. It is the version of the rules that can be run, fuzzed, and checked, so the contracts have something exact to be tested against.

| Module | What it does |
| --- | --- |
| `commit` | Merkle commitments over the files of a run. One 32 byte root commits to every input and output, with inclusion proofs. RFC 6962 tree, checked against the published test vectors. |
| `assignment` | Deterministic, verifiable random draws for runners and reviewer panels. Unbiased, order independent, with conflict rules built in. |
| `incentives` | Questions the settlement parameters can be asked: the smallest runner stake that makes honesty beat faking, how much griefing the rules absorb, and what a lone reviewer gives up by defecting. Computed with the settlement engine. |
| `settlement` | Integer payout and slashing rules from `docs/mechanism.md`, with conservation checked across tens of thousands of random cases. |

See [docs/reference-model.md](../../docs/reference-model.md) for the design and the guarantees each module gives.

## Install and test

```bash
cd packages/protocol
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## Commit a run

```bash
dotsci-protocol commit examples/demo-claim/data
dotsci-protocol prove  examples/demo-claim/data measurements.csv > proof.json
dotsci-protocol verify 0x<root from the commit step> proof.json
```

## Explore stake sizes

```bash
dotsci-protocol explore --bounty 1000 --honest-cost 100 \
  --p-catch 0.05,0.1,0.3 --runner-slash-bps 5000 --wrongful-loss 0.02
```

These are thresholds for the numbers you give, not recommended values.

## Library

```python
from dotsci_protocol.commit import commit_directory
from dotsci_protocol.assignment import draw, verify_draw
from dotsci_protocol.settlement import Case, Params, settle

commitment = commit_directory("out")
proof = commitment.prove("results.json")
assert proof.verify(commitment.root)

picks = draw(seed, "claim-1", "reviewer", agent_ids, count=5)
assert verify_draw(seed, "claim-1", "reviewer", agent_ids, picks)
```

## What is not decided

Settlement parameters have no defaults on purpose. The real values are open decisions in `docs/mechanism.md`. The seed for assignment comes from a randomness source that is also still open. This package takes both as inputs.

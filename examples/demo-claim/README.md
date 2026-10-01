# Demo claim

A small, self-contained claim for trying the runner end to end. **It is fictional.** The data is synthetic and there is no paper behind it. It exists so you can see the full loop on something that runs in seconds.

What is here:

- `manifest.json`: the replication manifest (`demo-0001`)
- `data/measurements.csv`: 200 synthetic measurements, control and treatment
- `analysis.py`: the analysis, standard library only. Writes `results.json`

The manifest's `commit` and `image_digest` are placeholders. Replace them with a real commit and a real image digest before using `run` with Docker.

## Try it without Docker

From the repository root:

```bash
cd packages/runner && pip install -e ".[dev]" && cd ../..

dotsci-runner validate examples/demo-claim/manifest.json
dotsci-runner verify-inputs examples/demo-claim/manifest.json --data-dir examples/demo-claim/data

cd examples/demo-claim
DOTSCI_OUT_DIR=./out python analysis.py
cd ../..

dotsci-runner compare examples/demo-claim/manifest.json \
  --results examples/demo-claim/out/results.json --out run.json
```

The last command prints `reproduced` and writes a run record to `run.json`.

## Try it in the sandbox

Build an image that contains Python, pin it by digest, set the manifest's `image_digest` and `commit`, then follow [sandbox/README.md](../../sandbox/README.md). Use `--dry-run` first to see the exact docker command.

## Make it fail on purpose

Change a target's `published` value in the manifest to `0.9` and run `compare` again. The outcome becomes `not_reproduced`, and the run record shows which comparison differed and by how much.

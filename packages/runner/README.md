# dotsci-runner

Toolkit for DotSci runners and challengers.

What it does today:

- Validates a replication manifest against the schema
- Verifies input file hashes against a manifest
- Checks that a code directory is a clean checkout of the pinned commit
- Runs a manifest's entrypoint inside a locked-down container (see `../../sandbox/README.md`)
- Compares rerun values to published targets using each target's tolerance
- Compares two run records of the same claim and states exactly where they differ (`diff`)
- Measures how much honest reruns vary and what tolerance that implies (`calibrate`)
- Writes JSONL logs in the DotSci format
- Produces a run record

What it does not do: fetch data, clone code, or build images. The host pipeline does those before `run`, and must verify hashes before using anything it downloads. It also does not talk to a network service yet.

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## CLI

```bash
dotsci-runner validate MANIFEST
dotsci-runner verify-inputs MANIFEST --data-dir DIR
dotsci-runner compare MANIFEST --results RESULTS.json [--job-id ID] [--role runner|challenger] [--out RUN.json]
dotsci-runner diff RUN_A.json RUN_B.json [--json]
dotsci-runner calibrate RUN1.json RUN2.json ... [--margin 2.0] [--json]
dotsci-runner run MANIFEST --code-dir DIR --data-dir DIR --out-dir DIR --image REPO@sha256:DIGEST [--dry-run] [--record RUN.json]
```

`RESULTS.json` maps each target name to the rerun value:

```json
{ "primary_effect": 0.412, "sample_size": 1200 }
```

`run` needs Docker. Use `--dry-run` to run the checks and print the docker command without starting anything. Other useful options: `--cpus`, `--memory`, `--pids`, `--tmp-size`, `--runtime runsc`, `--log-file`.

Exit codes: `0` reproduced, `1` any other outcome or invalid input, `2` usage error or docker failure.

## Library

```python
from dotsci_runner.manifest import load_manifest
from dotsci_runner.compare import compare_targets

manifest = load_manifest("manifest.json")
comparisons, outcome = compare_targets(manifest["targets"], {"primary_effect": 0.412})
```

## Layout

- `manifest.py`: load and validate manifests
- `hashing.py`: file hashing and input verification
- `compare.py`: tolerance rules and outcome
- `sandbox.py`: docker command construction, image and checkout checks, execution
- `job.py`: the end to end run flow
- `dispute.py`: compare two run records and produce dispute evidence
- `record.py`: run record builder
- `runlog.py`: JSONL logging
- `cli.py`: command line

## Schemas

The schemas in `src/dotsci_runner/schemas/` are copies of the ones in the repository's `spec/` folder. A test checks that they stay identical.

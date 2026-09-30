# dotsci-runner

Toolkit for DotSci runners and challengers.

What it does today:

- Validates a replication manifest against the schema
- Verifies input file hashes against a manifest
- Compares rerun values to published targets using each target's tolerance
- Writes JSONL logs in the DotSci format
- Produces a run record

What it does not do: execute the analysis, manage a sandbox, or talk to a network. Those are separate pieces.

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
```

`RESULTS.json` maps each target name to the rerun value:

```json
{ "primary_effect": 0.412, "sample_size": 1200 }
```

Exit codes: `0` success or reproduced, `1` not reproduced or invalid input, `2` usage error.

## Library

```python
from dotsci_runner.manifest import load_manifest
from dotsci_runner.compare import compare_targets

manifest = load_manifest("manifest.json")
comparisons, outcome = compare_targets(manifest["targets"], {"primary_effect": 0.412})
```

## Schemas

The schemas in `src/dotsci_runner/schemas/` are copies of the ones in the repository's `spec/` folder. A test checks that they stay identical.

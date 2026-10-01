# Writing a claim

A claim is one published result plus a manifest that lets anyone rerun it. This guide walks through writing a good one. The field reference is in `manifest-spec.md`.

## Pick a result that can be rerun

Good first claims have:

- **Public data** you are allowed to redistribute, or that anyone can download from a stable source
- **Public code**, or an analysis you can write down fully
- **A number to check**, such as an effect size, a coefficient, a sample size, or a summary statistic from a table
- **A runtime of minutes to hours** on ordinary hardware

Skip results that need private data, special instruments, or hardware you cannot name. Those are out of scope for now.

## Steps

### 1. Pin the data
Download each input file, compute its SHA-256, and list it in `datasets` with its name and license.

```bash
shasum -a 256 measurements.csv        # macOS
sha256sum measurements.csv            # Linux
```

If the source can change or disappear, mirror the file somewhere stable and put that URL in `url`. The hash is what counts. If the file changes, runs stop with `input_mismatch`.

### 2. Pin the code
Give the repository and a full commit hash. Tags and branch names are not accepted because they move.

### 3. Pin the environment
Build a container image with the dependencies, push it, and record its digest (`sha256:...`). The runner only accepts an image reference pinned by digest (`repository@sha256:...`) that matches the manifest. Tags are rejected. List the main dependency versions in `dependencies` so readers can see them.

### 4. Fix the randomness
If the analysis uses random numbers, choose a seed and put it in `environment.seed`. The runner passes it as `DOTSCI_SEED`. Make sure your code actually reads it.

### 5. Write the entrypoint
The command runs inside the sandbox. It reads data from `DOTSCI_DATA_DIR` and must write `results.json` to `DOTSCI_OUT_DIR`: one JSON object mapping each target name to a number. There is no network access, so everything the analysis needs must be in the code, the data, or the image.

### 6. Set the targets
For each value you want checked, give:

- `name`, which must match a key in `results.json`
- `published`, the value as reported
- `source`, where it appears (for example "Table 2, row 1")
- `tolerance`, either `absolute` or `relative`

### 7. Choose tolerances honestly
Tolerance is what "the same" means for this claim. A few guidelines:

- Counts and sample sizes: absolute tolerance of `0`.
- Values the paper rounds: set the tolerance to at least the rounding. A value reported as `0.41` is within `0.005` of anything that rounds to it.
- Stochastic methods: widen the tolerance enough that honest reruns with the pinned seed agree, and no wider. If two honest runs of the same manifest disagree beyond your tolerance, the claim is a `spec_issue`.
- Do not tune a tolerance to make a particular result pass or fail. It is part of the claim, and anyone can read it.

### 8. Check it locally
```bash
dotsci-runner validate manifest.json
dotsci-runner verify-inputs manifest.json --data-dir ./data
# run your analysis, then:
dotsci-runner compare manifest.json --results out/results.json
```

Then try the sandbox with `--dry-run` to see the exact container command. See `sandbox/README.md`.

## Checklist

- [ ] Data is public or redistributable, with a license noted
- [ ] Every input file has a SHA-256 in the manifest
- [ ] Code is pinned to a full commit
- [ ] Image is pinned by digest
- [ ] Seed is set if the analysis is random, and the code reads it
- [ ] The entrypoint writes `results.json` with every target name
- [ ] Each target cites where it appears in the paper
- [ ] Tolerances are explained and not tuned to an outcome
- [ ] `dotsci-runner validate` passes
- [ ] A local rerun ends in `reproduced`, or you know why it does not

## Language

Describe results as reproduced or not reproduced under the published spec. Do not describe a paper as wrong, and do not describe authors at all. The claim is about a number and a method.

## A worked example

`examples/demo-claim` is a small, fictional claim you can run in seconds. Use it as a template.

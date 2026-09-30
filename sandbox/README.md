# Sandbox

Reference setup for running a replication manifest in isolation.

**Status.** The docker command construction and the job orchestration are covered by tests that use a stand-in `docker` executable. They have not yet been run against a real Docker daemon, and the Dockerfiles have not been built in CI. Treat the isolation settings as a reviewed starting point, not a verified boundary. An integration test against real Docker is the next step.

## What the sandbox applies

`dotsci-runner run` starts the manifest's entrypoint with these settings:

| Setting | Why |
| --- | --- |
| `--network none` | No network, so the analysis cannot fetch anything the manifest did not pin or send data out |
| `--read-only` root filesystem | The image cannot be modified at run time |
| `--tmpfs /tmp` with a size cap | The only scratch space, discarded on exit |
| `--cap-drop ALL`, `--security-opt no-new-privileges` | No Linux capabilities and no privilege escalation |
| `--user 10001:10001` | Non-root |
| `--pids-limit`, `--memory`, `--memory-swap` (equal), `--cpus`, `--ulimit core=0` | Bounds on forks, memory, CPU, and core dumps |
| `--init` | Reaps stray processes |
| Code and data mounted read-only | The analysis cannot alter what was verified |
| Output directory mounted read-write, and must start empty | The only place results can go |
| Timeout with explicit `docker kill` | A hung run cannot hold the job open |
| Image must be referenced by digest | A tag can move, so tags are rejected |

Before anything runs, the host also checks that dataset hashes match the manifest, that the code directory is a clean checkout of the pinned commit (no modified, untracked, or ignored files), and that the image digest matches the manifest.

## What it does not give you

- **A hard security boundary.** Containers share the host kernel. For untrusted analysis code in production, use a stronger runtime such as gVisor (`--runtime runsc`) or a microVM.
- **Disk limits on the output directory.** It lives on the host. Put it on a size-limited filesystem.
- **Fetching and checking out.** The host step that downloads data and clones code runs outside the sandbox. It must verify hashes before use and never execute anything from the checkout.
- **Dependencies at run time.** With no network, every dependency has to be baked into the image at build time.
- **Determinism.** GPU kernels, threading, and floating point can differ across hardware. State hardware needs in the claim or pick tolerances that account for it.

## Execution contract

Inside the container:

- Code is at `/work/code`, read-only. The working directory is `/work/code`, or a subfolder if the manifest sets `working_dir`.
- Data is at `/work/data`, read-only, and the path is in `DOTSCI_DATA_DIR`.
- Output goes to `/work/out`, and the path is in `DOTSCI_OUT_DIR`.
- `DOTSCI_SEED` is set when the manifest has a seed.
- `HOME` and scratch space are `/tmp`.
- The entrypoint command runs with `sh -c`.

The analysis must write `results.json` to the output directory: a JSON object mapping each target name to a number.

## How results are recorded

| Situation | Outcome |
| --- | --- |
| Dataset hash, code checkout, or image digest does not match the manifest | `input_mismatch` |
| Entrypoint exits non-zero, times out, or cannot be started inside the container | `spec_issue` |
| `results.json` is missing, malformed, or too large, or the output contains a symlink | `spec_issue` |
| All targets within tolerance | `reproduced` |
| Any target outside tolerance or missing | `not_reproduced` |

If docker itself fails to start the container (exit code 125), no record is written and the command exits with an error, because that is an operator problem and not a finding about the claim.

## Building images

```bash
docker build \
  --build-arg BASE_IMAGE=python:3.11-slim@sha256:<digest> \
  -t dotsci-python-base \
  -f sandbox/images/python/Dockerfile \
  sandbox/images/python
```

For a claim, copy `claim.Dockerfile.example`, add a `requirements.lock` with hashes, build it, push it, and put the pushed digest in the manifest. R and other languages follow the same pattern: start from a pinned base image, create the same non-root user, and install pinned packages at build time.

## Running a job

Check everything and print the exact docker command without running it:

```bash
dotsci-runner run manifest.json \
  --code-dir ./checkout \
  --data-dir ./data \
  --out-dir ./out \
  --image registry.example.org/claim-0001@sha256:<digest> \
  --dry-run
```

Run it:

```bash
dotsci-runner run manifest.json \
  --code-dir ./checkout \
  --data-dir ./data \
  --out-dir ./out \
  --image registry.example.org/claim-0001@sha256:<digest> \
  --job-id job-0001 \
  --record run.json \
  --log-file run.log.jsonl
```

Add `--runtime runsc` to use gVisor. Exit codes: `0` reproduced, `1` any other outcome, `2` usage or docker error.

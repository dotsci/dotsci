"""Command line access to run commitments: commit a directory, prove a file, verify a proof."""

from __future__ import annotations

import argparse
import json
import sys

from fractions import Fraction

from .commit import CommitError, InclusionProof, commit_directory
from .incentives import min_runner_stake


def _cmd_commit(args: argparse.Namespace) -> int:
    try:
        commitment = commit_directory(args.directory)
    except CommitError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"root": commitment.bytes32, "size": commitment.size,
                      "files": [{"path": p, "sha256": d} for p, d in commitment.files]}, indent=2))
    return 0


def _cmd_prove(args: argparse.Namespace) -> int:
    try:
        commitment = commit_directory(args.directory)
        proof = commitment.prove(args.path)
    except CommitError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"root": commitment.bytes32, "path": proof.path, "sha256": proof.sha256,
                      "index": proof.index, "size": proof.size, "siblings": list(proof.siblings)}, indent=2))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        data = json.loads(open(args.proof, encoding="utf-8").read())
        proof = InclusionProof(path=data["path"], sha256=data["sha256"], index=int(data["index"]),
                               size=int(data["size"]), siblings=tuple(data["siblings"]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"unreadable proof: {exc}", file=sys.stderr)
        return 1
    if proof.verify(args.root):
        print(f"ok: {proof.path} is committed to by {args.root}")
        return 0
    print("proof does not match the root", file=sys.stderr)
    return 1


def _cmd_explore(args: argparse.Namespace) -> int:
    try:
        probabilities = [Fraction(x.strip()) for x in args.p_catch.split(",") if x.strip()]
    except ValueError:
        print("--p-catch must be a comma separated list of numbers between 0 and 1", file=sys.stderr)
        return 1
    if not probabilities or any(not 0 <= p <= 1 for p in probabilities):
        print("--p-catch values must be between 0 and 1", file=sys.stderr)
        return 1
    w = Fraction(args.wrongful_loss)
    print(f"bounty={args.bounty} honest_cost={args.honest_cost} runner_slash_bps={args.runner_slash_bps} wrongful_loss={float(w)}")
    print(f"{'p_catch':>8}  {'min runner stake':>18}")
    for p in probabilities:
        stake = min_runner_stake(args.bounty, args.honest_cost, p, args.runner_slash_bps, w)
        shown = "cannot deter" if stake is None else str(stake)
        print(f"{float(p):>8.3f}  {shown:>18}")
    print("These are thresholds for an example, not recommended values.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dotsci-protocol", description="DotSci run commitments")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("commit", help="print the Merkle root and file list for a directory")
    p.add_argument("directory")
    p.set_defaults(func=_cmd_commit)
    p = sub.add_parser("prove", help="print an inclusion proof for one file in a directory")
    p.add_argument("directory")
    p.add_argument("path")
    p.set_defaults(func=_cmd_prove)
    p = sub.add_parser("verify", help="check an inclusion proof against a root")
    p.add_argument("root")
    p.add_argument("proof", help="JSON file written by the prove command")
    p.set_defaults(func=_cmd_verify)
    p = sub.add_parser("explore", help="minimum runner stake that makes honest running beat faking, for given odds")
    p.add_argument("--bounty", type=int, required=True)
    p.add_argument("--honest-cost", type=int, required=True)
    p.add_argument("--p-catch", required=True, help="comma separated chances a fake result is caught, for example 0.1,0.3,0.5")
    p.add_argument("--runner-slash-bps", type=int, required=True)
    p.add_argument("--wrongful-loss", default="0", help="chance an honest run is wrongly overturned (default 0)")
    p.set_defaults(func=_cmd_explore)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

"""Command line access to run commitments: commit a directory, prove a file, verify a proof."""

from __future__ import annotations

import argparse
import json
import sys

from .commit import CommitError, InclusionProof, commit_directory


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
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

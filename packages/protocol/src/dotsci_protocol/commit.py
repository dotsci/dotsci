"""Merkle commitments over run files.

A run record can commit to every input and output file with one 32 byte root.
Anyone holding a file and a short proof can show that the file was part of the run,
without the other files.

The tree is the RFC 6962 Merkle tree over SHA-256, with domain separation between
leaves (0x00 prefix) and interior nodes (0x01 prefix). That construction is
standardized, widely implemented, and resists second preimage attacks. This module
checks itself against the published RFC 6962 test vectors.

A proof binds a file and its position to the root. It does not authenticate the total
number of leaves, so register the size (see Commitment.size) next to the root and take
it from there, never from the prover.

File leaves are:  uint32_be(len(path)) || path (UTF-8) || sha256(file contents)
Leaves are ordered by path bytes, so the same files always give the same root.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


class CommitError(ValueError):
    """Raised for unusable paths, symlinks, or malformed proofs."""


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(data: bytes) -> bytes:
    return _h(LEAF_PREFIX + data)


def node_hash(left: bytes, right: bytes) -> bytes:
    return _h(NODE_PREFIX + left + right)


def _split(n: int) -> int:
    """Largest power of two strictly less than n (n >= 2)."""
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    """RFC 6962 Merkle Tree Hash of already prepared leaf data."""
    n = len(leaves)
    if n == 0:
        return _h(b"")
    if n == 1:
        return leaf_hash(leaves[0])
    k = _split(n)
    return node_hash(merkle_root(leaves[:k]), merkle_root(leaves[k:]))


def audit_path(leaves: Sequence[bytes], index: int) -> list[bytes]:
    """RFC 6962 audit path for the leaf at index."""
    n = len(leaves)
    if not 0 <= index < n:
        raise CommitError("leaf index out of range")
    if n == 1:
        return []
    k = _split(n)
    if index < k:
        return audit_path(leaves[:k], index) + [merkle_root(leaves[k:])]
    return audit_path(leaves[k:], index - k) + [merkle_root(leaves[:k])]


def _root_from_path(index: int, size: int, leaf: bytes, path: Sequence[bytes]) -> bytes:
    if size == 1:
        if path:
            raise CommitError("proof is longer than the tree allows")
        return leaf
    if not path:
        raise CommitError("proof is shorter than the tree requires")
    k = _split(size)
    *rest, sibling = path
    if index < k:
        return node_hash(_root_from_path(index, k, leaf, rest), sibling)
    return node_hash(sibling, _root_from_path(index - k, size - k, leaf, rest))


def verify_inclusion(root: bytes, size: int, index: int, leaf_data: bytes, path: Sequence[bytes]) -> bool:
    """True if leaf_data is leaf number index of a tree with this root and size."""
    if size < 1 or not 0 <= index < size:
        return False
    try:
        return _root_from_path(index, size, leaf_hash(leaf_data), path) == root
    except CommitError:
        return False


# ---- file commitments -------------------------------------------------------


def _file_leaf(path: str, sha256_hex: str) -> bytes:
    encoded = path.encode("utf-8")
    digest = bytes.fromhex(sha256_hex)
    if len(digest) != 32:
        raise CommitError(f"not a SHA-256 digest: {sha256_hex!r}")
    return len(encoded).to_bytes(4, "big") + encoded + digest


def _check_path(path: str) -> None:
    p = PurePosixPath(path)
    if not path or p.is_absolute() or ".." in p.parts or "\\" in path or str(p) != path:
        raise CommitError(f"invalid path: {path!r}")


@dataclass(frozen=True)
class Commitment:
    """A root plus the ordered list of files it commits to."""

    root: str  # 64 lowercase hex characters
    files: tuple[tuple[str, str], ...]  # (path, sha256 hex), sorted by path bytes

    @property
    def size(self) -> int:
        return len(self.files)

    @property
    def bytes32(self) -> str:
        """The root as 0x-prefixed hex, ready for a contract call."""
        return "0x" + self.root

    def _leaves(self) -> list[bytes]:
        return [_file_leaf(p, d) for p, d in self.files]

    def prove(self, path: str) -> "InclusionProof":
        for index, (name, digest) in enumerate(self.files):
            if name == path:
                proof = audit_path(self._leaves(), index)
                return InclusionProof(
                    path=name,
                    sha256=digest,
                    index=index,
                    size=self.size,
                    siblings=tuple(s.hex() for s in proof),
                )
        raise CommitError(f"path is not in the commitment: {path!r}")


@dataclass(frozen=True)
class InclusionProof:
    path: str
    sha256: str
    index: int
    size: int
    siblings: tuple[str, ...]

    def verify(self, root_hex: str) -> bool:
        """True if this file, at this index, is committed to by root_hex."""
        try:
            root = bytes.fromhex(root_hex.removeprefix("0x"))
            _check_path(self.path)
            leaf = _file_leaf(self.path, self.sha256)
            siblings = [bytes.fromhex(s) for s in self.siblings]
        except (ValueError, CommitError):
            return False
        return verify_inclusion(root, self.size, self.index, leaf, siblings)


def commit_files(hashes: Mapping[str, str]) -> Commitment:
    """Commit to a mapping of relative path to SHA-256 hex digest."""
    for path in hashes:
        _check_path(path)
    ordered = tuple(sorted(((p, d.lower()) for p, d in hashes.items()), key=lambda item: item[0].encode("utf-8")))
    leaves = [_file_leaf(p, d) for p, d in ordered]
    return Commitment(root=merkle_root(leaves).hex(), files=ordered)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def commit_directory(directory: str | Path) -> Commitment:
    """Hash every file under a directory and commit to the result.

    Symlinks are rejected, never followed, so a run cannot point the commitment at
    files outside its own output.
    """
    base = Path(directory)
    if not base.is_dir():
        raise CommitError(f"not a directory: {directory}")
    hashes: dict[str, str] = {}
    for current, dirs, names in os.walk(base, followlinks=False):
        for name in list(dirs) + names:
            full = Path(current) / name
            if full.is_symlink():
                raise CommitError(f"symlinks are not allowed: {full.relative_to(base)}")
        for name in names:
            full = Path(current) / name
            hashes[full.relative_to(base).as_posix()] = sha256_file(full)
    return commit_files(hashes)

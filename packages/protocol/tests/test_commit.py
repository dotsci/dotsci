import hashlib
import os

import pytest

from dotsci_protocol.commit import (
    CommitError,
    InclusionProof,
    audit_path,
    commit_directory,
    commit_files,
    leaf_hash,
    merkle_root,
    verify_inclusion,
)

# Published RFC 6962 (Certificate Transparency) test vectors: roots of the first n leaves.
RFC_LEAVES = [
    b"",
    b"\x00",
    b"\x10",
    b"\x20\x21",
    b"\x30\x31",
    b"\x40\x41\x42\x43",
    bytes(range(0x50, 0x58)),
    bytes(range(0x60, 0x70)),
]
RFC_ROOTS = {
    0: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    1: "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
    2: "fac54203e7cc696cf0dfcb42c92a1d9dbaf70ad9e621f4bd8d98662f00e3c125",
    3: "aeb6bcfe274b70a14fb067a5e5578264db0fa9b51af5e0ba159158f329e06e77",
    4: "d37ee418976dd95753c1c73862b9398fa2a2cf9b4ff0fdfe8b30cd95209614b7",
    5: "4e3bbb1f7b478dcfe71fb631631519a3bca12c9aefca1612bfce4c13a86264d4",
    6: "76e67dadbcdf1e10e1b74ddc608abd2f98dfb16fbce75277b5232a127f2087ef",
    7: "ddb89be403809e325750d3d263cd78929c2942b7942a34b77e122c9594a74c8c",
    8: "5dc9da79a70659a9ad559cb701ded9a2ab9d823aad2f4960cfe370eff4604328",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sample(n: int) -> dict[str, str]:
    return {f"out/file{i:02d}.txt": sha(f"content {i}") for i in range(n)}


def test_rfc6962_vectors():
    for n, expected in RFC_ROOTS.items():
        assert merkle_root(RFC_LEAVES[:n]).hex() == expected


def test_every_leaf_of_every_small_tree_has_a_valid_proof():
    for size in range(1, 25):
        leaves = [bytes([i]) * (i + 1) for i in range(size)]
        root = merkle_root(leaves)
        for index in range(size):
            path = audit_path(leaves, index)
            assert verify_inclusion(root, size, index, leaves[index], path)


def test_proof_length_is_logarithmic():
    leaves = [bytes([i % 256, i // 256]) for i in range(1000)]
    assert max(len(audit_path(leaves, i)) for i in (0, 499, 999)) <= 10


def test_wrong_leaf_index_or_size_fails():
    leaves = [bytes([i]) for i in range(11)]
    root = merkle_root(leaves)
    path = audit_path(leaves, 4)
    assert verify_inclusion(root, 11, 4, leaves[4], path)
    assert not verify_inclusion(root, 11, 4, b"tampered", path)
    assert not verify_inclusion(root, 11, 5, leaves[4], path)
    assert not verify_inclusion(root, 17, 4, leaves[4], path)
    assert not verify_inclusion(root, 11, 4, leaves[4], path[:-1])
    assert not verify_inclusion(root, 11, 4, leaves[4], path + [b"\x00" * 32])
    assert not verify_inclusion(root, 11, 11, leaves[4], path)
    assert not verify_inclusion(root, 0, 0, leaves[4], path)


def test_interior_node_cannot_pass_as_a_leaf():
    a, b = b"a", b"b"
    root_two = merkle_root([a, b])
    forged_leaf = leaf_hash(a) + leaf_hash(b)
    assert merkle_root([forged_leaf]) != root_two


def test_commitment_does_not_depend_on_input_order():
    items = sample(9)
    reversed_items = dict(reversed(list(items.items())))
    assert commit_files(items).root == commit_files(reversed_items).root


def test_changing_a_file_or_a_name_changes_the_root():
    items = sample(5)
    base = commit_files(items).root
    changed = dict(items)
    changed["out/file02.txt"] = sha("different")
    assert commit_files(changed).root != base
    renamed = dict(items)
    renamed["out/renamed.txt"] = renamed.pop("out/file02.txt")
    assert commit_files(renamed).root != base
    extra = dict(items)
    extra["out/extra.txt"] = sha("more")
    assert commit_files(extra).root != base


def test_file_proofs_verify_against_the_root():
    commitment = commit_files(sample(13))
    for path, _ in commitment.files:
        proof = commitment.prove(path)
        assert proof.verify(commitment.root)
        assert proof.verify(commitment.bytes32)


def test_a_proof_does_not_verify_for_another_file_or_root():
    commitment = commit_files(sample(6))
    proof = commitment.prove("out/file01.txt")
    other = commit_files(sample(7))
    assert not proof.verify(other.root)
    forged = InclusionProof(
        path=proof.path, sha256=sha("not the real file"), index=proof.index, size=proof.size, siblings=proof.siblings
    )
    assert not forged.verify(commitment.root)
    moved = InclusionProof(
        path="out/file02.txt", sha256=proof.sha256, index=proof.index, size=proof.size, siblings=proof.siblings
    )
    assert not moved.verify(commitment.root)
    assert not InclusionProof("../x", proof.sha256, 0, 1, ()).verify(commitment.root)


def test_proof_for_missing_path_raises():
    with pytest.raises(CommitError):
        commit_files(sample(3)).prove("nope.txt")


def test_bad_paths_are_rejected():
    for bad in ("", "/etc/passwd", "../x", "a/../b", "a\\b", "a//b", "./a"):
        with pytest.raises(CommitError):
            commit_files({bad: sha("x")})


def test_empty_commitment_is_the_empty_tree_hash():
    assert commit_files({}).root == RFC_ROOTS[0]


def test_directory_commitment_matches_file_commitment(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "results.json").write_text('{"a": 1}')
    (tmp_path / "sub" / "plot.txt").write_text("plot")
    by_dir = commit_directory(tmp_path)
    by_hand = commit_files(
        {
            "results.json": hashlib.sha256(b'{"a": 1}').hexdigest(),
            "sub/plot.txt": hashlib.sha256(b"plot").hexdigest(),
        }
    )
    assert by_dir.root == by_hand.root
    assert [p for p, _ in by_dir.files] == ["results.json", "sub/plot.txt"]


def test_directory_commitment_rejects_symlinks(tmp_path):
    (tmp_path / "real.txt").write_text("x")
    os.symlink(tmp_path / "real.txt", tmp_path / "link.txt")
    with pytest.raises(CommitError):
        commit_directory(tmp_path)


def test_missing_directory_is_rejected(tmp_path):
    with pytest.raises(CommitError):
        commit_directory(tmp_path / "nope")


def test_tree_size_is_not_authenticated_by_the_proof():
    """A proof binds a leaf and its index to the root, not the total size.

    Leaf 4 has the same path in trees of 11 and 12 leaves, so verifying with either
    size can succeed for a root that really is one of them. Register the size next to
    the root, and take the size from there, never from the prover.
    """
    leaves = [bytes([i]) for i in range(11)]
    root = merkle_root(leaves)
    path = audit_path(leaves, 4)
    assert verify_inclusion(root, 11, 4, leaves[4], path)
    assert verify_inclusion(root, 12, 4, leaves[4], path)

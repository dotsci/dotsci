# Conformance vectors

Language neutral test vectors for the parts of DotSci that other implementations must reproduce byte for byte: a Solidity contract, a TypeScript client, another runner.

| File | Pins down |
| --- | --- |
| `manifest-hash.json` | Canonical JSON of a manifest and its SHA-256 |
| `merkle.json` | RFC 6962 trees, audit paths, inclusion verdicts (valid and invalid), and the file leaf format |
| `assignment.json` | The seeded word stream, rejection sampling, and full draws |
| `settlement.json` | Settlement payouts for every case kind, including rounding dust, huge amounts, ties and invalid input |

## Using them

Load a file, run each case through your implementation, compare. Every case carries its expected output. Cases marked `"error"` must be rejected, and for settlement the error says which kind: `tie` or `invalid`.

Amounts and 64 bit words are decimal strings, so values past 2^53 (token amounts, `uint256`) survive any JSON parser. Hex fields are lowercase without a `0x` prefix.

## Rules the vectors pin down

**Manifest hash.** Keys sorted recursively by code point, separators `,` and `:` with no whitespace, UTF-8 with non-ASCII characters left unescaped, NaN and infinity rejected, SHA-256 of the resulting bytes. Number text follows the shortest round-trip form of Python's `json` module: `5.0` stays `5.0` and `1e-07` stays `1e-07`. A port in a language that prints `5.0` as `5` would hash differently, and `floats_use_shortest_repr` exists to catch that. Prefer integers and strings in manifests that other languages must hash.

**Merkle.** RFC 6962: leaf hash `SHA-256(0x00 || data)`, node hash `SHA-256(0x01 || left || right)`, split at the largest power of two below n, empty tree is `SHA-256("")`. A file leaf is `uint32_be(len(path)) || path || sha256(file)`, ordered by path bytes. A proof binds a file and index to a root and does not authenticate the tree size, so take the size from the registered commitment. The `interior_node_as_leaf` case shows why the prefixes matter.

**Assignment.** Word k comes from `SHA-256(domain || lp(seed) || lp(claim) || lp(role) || uint64_be(block))`, four 64 bit words per block, where `lp` is a 4 byte big endian length prefix and the domain is `dotsci/assign/v1`. `uniform_below(n)` rejects words at or above `2^64 - (2^64 mod n)`. A draw sorts and de-duplicates candidates, then runs a partial Fisher-Yates.

**Settlement.** Integer basis point math with floor division, and the conservation invariant: everything that went in comes out as a payout, to the vault, or as treasury dust. The parameter sets in the file are test values. They are not proposals, the real values are open decisions.

## Two checks

The reference packages replay the vectors in their own tests. `verify.py` replays them with a separate implementation that imports nothing from DotSci:

```bash
python spec/vectors/verify.py
```

It reproduces every vector using only the standard library, and verifies Merkle proofs iteratively where the reference is recursive. If the two ever disagree, one of them is wrong. It is also a compact reference for a port.

## Regenerating

The files come from the reference code:

```bash
python tools/gen_vectors.py          # rewrite
python tools/gen_vectors.py --check  # fail if the files are stale (CI runs this)
```

Changing a vector is changing the specification, so a diff here should always be reviewed as one.

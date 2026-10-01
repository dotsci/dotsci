# Manifest spec

Draft v0.1. The machine-readable definition is `spec/manifest.schema.json`. This page explains the fields.

## Purpose

A manifest pins everything a replication depends on, so two parties running it should reach the same answer.

## Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `spec_version` | yes | Spec version, currently `"0.1"` |
| `claim_id` | yes | Unique id for the claim |
| `paper` | yes | Title, plus optional authors, DOI, URL, field |
| `datasets` | yes | Each input file with name, SHA-256, optional URL and license |
| `code` | yes | Repository and commit |
| `environment` | yes | Container image digest, optional dependency versions, seed, timeout |
| `entrypoint` | yes | The command to run and optional working directory |
| `targets` | yes | Values to compare, each with published value, optional source, and tolerance |

## Rules

1. **Hashes are lowercase hex SHA-256.** Image digests use the `sha256:` prefix.
2. **Commits are pinned.** Branch names and tags are not accepted, because they move.
3. **One seed.** If the analysis uses randomness, the seed is fixed in the manifest. If results depend on hardware, state it in the paper's entry or split the claim.
4. **Tolerance is explicit.** Every target has an `absolute` or `relative` tolerance. There is no default.
5. **Targets cite their source.** Use the `source` field to say where in the paper the value appears.

## Validating

```bash
dotsci-runner validate path/to/manifest.json
```

## Example

See `spec/examples/manifest.example.json`. It is fictional and uses placeholder hashes.

## Manifest hash

A claim is registered by the hash of its manifest. The hash is SHA-256 over the canonical form: keys sorted, compact separators (`,` and `:`), UTF-8 text, no NaN or infinity. Key order and whitespace in the source file do not matter.

```bash
dotsci-runner hash manifest.json             # sha256:<hex>
dotsci-runner hash manifest.json --bytes32   # 0x<hex>, ready for a contract call
```

Numbers are serialized in their shortest round-trip form. Other implementations must match this form exactly. If cross-language drift becomes a problem, the spec will move to RFC 8785 (JSON Canonicalization Scheme) in a new `spec_version`.

## Versioning

Breaking changes bump `spec_version`. Runners must reject manifests with a version they do not support.

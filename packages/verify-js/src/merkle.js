// RFC 6962 Merkle trees over SHA-256 and DotSci's file leaf format.
// Mirrors packages/protocol/src/dotsci_protocol/commit.py.

import { sha256, concat, equalBytes, fromHex, toHex, utf8 } from "./sha256.js";
import { compareCodePoints } from "./canonical.js";

export class CommitError extends Error {}

const LEAF = new Uint8Array([0]);
const NODE = new Uint8Array([1]);

export const leafHash = (data) => sha256(concat(LEAF, data));
export const nodeHash = (left, right) => sha256(concat(NODE, left, right));

function splitPoint(n) {
  let k = 1;
  while (k * 2 < n) k *= 2;
  return k;
}

/** Merkle tree hash of already prepared leaf data (Uint8Array items). */
export function merkleRoot(leaves) {
  const n = leaves.length;
  if (n === 0) return sha256(new Uint8Array(0));
  if (n === 1) return leafHash(leaves[0]);
  const k = splitPoint(n);
  return nodeHash(merkleRoot(leaves.slice(0, k)), merkleRoot(leaves.slice(k)));
}

/** Audit path for the leaf at index. */
export function auditPath(leaves, index) {
  const n = leaves.length;
  if (!Number.isInteger(index) || index < 0 || index >= n) throw new CommitError("leaf index out of range");
  if (n === 1) return [];
  const k = splitPoint(n);
  if (index < k) return [...auditPath(leaves.slice(0, k), index), merkleRoot(leaves.slice(k))];
  return [...auditPath(leaves.slice(k), index - k), merkleRoot(leaves.slice(0, k))];
}

/** Root implied by a leaf hash, its index, the tree size and an audit path. Null if the proof shape is wrong. */
function rootFromPath(index, size, leaf, path) {
  if (index >= size) return null;
  let fn = index;
  let sn = size - 1;
  let r = leaf;
  for (const p of path) {
    if (sn === 0) return null;
    if (fn % 2 === 1 || fn === sn) {
      r = nodeHash(p, r);
      if (fn % 2 === 0) {
        while (fn % 2 === 0 && fn !== 0) { fn = Math.floor(fn / 2); sn = Math.floor(sn / 2); }
      }
    } else {
      r = nodeHash(r, p);
    }
    fn = Math.floor(fn / 2);
    sn = Math.floor(sn / 2);
  }
  return sn === 0 ? r : null;
}

/** True if leafData is leaf number index of a tree with this root and size. Never throws. */
export function verifyInclusion(root, size, index, leafData, siblings) {
  if (!Number.isInteger(size) || !Number.isInteger(index) || size < 1 || index < 0 || index >= size) return false;
  const got = rootFromPath(index, size, leafHash(leafData), siblings);
  return got !== null && equalBytes(got, root);
}

// ---- file commitments -------------------------------------------------------

export function checkPath(path) {
  const bad = () => { throw new CommitError(`invalid path: ${JSON.stringify(path)}`); };
  if (typeof path !== "string" || path === "" || path.startsWith("/") || path.includes("\\")) bad();
  for (const part of path.split("/")) if (part === "" || part === "." || part === "..") bad();
}

/** uint32_be(len(path)) || path (UTF-8) || sha256(file) */
export function fileLeaf(path, sha256Hex) {
  const encoded = utf8(path);
  if (!/^[0-9a-fA-F]{64}$/.test(sha256Hex)) throw new CommitError(`not a SHA-256 digest: ${sha256Hex}`);
  const length = new Uint8Array(4);
  new DataView(length.buffer).setUint32(0, encoded.length);
  return concat(length, encoded, fromHex(sha256Hex));
}

function compareBytes(a, b) {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) return a[i] - b[i];
  return a.length - b.length;
}

/**
 * Commit to a mapping of relative path to SHA-256 hex digest.
 * Returns { root (hex), size, files: [[path, digest], ...] sorted by UTF-8 bytes of the path }.
 */
export function commitFiles(hashes) {
  const entries = Object.entries(hashes);
  for (const [path] of entries) checkPath(path);
  const files = entries
    .map(([p, d]) => [p, d.toLowerCase()])
    .sort((a, b) => compareBytes(utf8(a[0]), utf8(b[0])));
  const leaves = files.map(([p, d]) => fileLeaf(p, d));
  return { root: toHex(merkleRoot(leaves)), size: files.length, files, leaves };
}

/** Inclusion proof for one path of a commitment: { path, sha256, index, size, siblings (hex) }. */
export function proveFile(commitment, path) {
  const index = commitment.files.findIndex(([p]) => p === path);
  if (index < 0) throw new CommitError(`path is not in the commitment: ${JSON.stringify(path)}`);
  return {
    path,
    sha256: commitment.files[index][1],
    index,
    size: commitment.size,
    siblings: auditPath(commitment.leaves, index).map(toHex),
  };
}

/** True if the proof's file, at its index, is committed to by rootHex. Never throws. */
export function verifyFileProof(proof, rootHex) {
  try {
    const root = fromHex(rootHex.replace(/^0x/, ""));
    checkPath(proof.path);
    return verifyInclusion(root, proof.size, proof.index, fileLeaf(proof.path, proof.sha256), proof.siblings.map(fromHex));
  } catch {
    return false;
  }
}

export { compareCodePoints };

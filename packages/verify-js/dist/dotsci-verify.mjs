// DotSci verification library, single file build of packages/verify-js/src. Do not edit by hand.
// Rebuild with: node scripts/bundle.mjs

// ---- sha256.js ------------------------------------------------------
// Pure JavaScript SHA-256 (FIPS 180-4). Synchronous, so the same code runs in a
// browser and in Node without Web Crypto's async API. Checked against Node's
// crypto module in test/sha256.test.js.

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

const rotr = (x, n) => (x >>> n) | (x << (32 - n));

/** SHA-256 of a Uint8Array. Returns a 32 byte Uint8Array. */
function sha256(data) {
  if (!(data instanceof Uint8Array)) throw new TypeError("sha256 expects a Uint8Array");
  const bitLength = data.length * 8;
  const paddedLength = (((data.length + 9 + 63) >> 6) << 6);
  const buffer = new Uint8Array(paddedLength);
  buffer.set(data);
  buffer[data.length] = 0x80;
  const view = new DataView(buffer.buffer);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000));
  view.setUint32(paddedLength - 4, bitLength >>> 0);

  const h = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const w = new Uint32Array(64);
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(offset + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (hh + S1 + ch + K[i] + w[i]) | 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) | 0;
      hh = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
  }
  const out = new Uint8Array(32);
  const outView = new DataView(out.buffer);
  for (let i = 0; i < 8; i++) outView.setUint32(i * 4, h[i]);
  return out;
}

const toHex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");

function fromHex(hex) {
  if (typeof hex !== "string" || hex.length % 2 !== 0 || !/^[0-9a-fA-F]*$/.test(hex)) {
    throw new Error(`not hex: ${hex}`);
  }
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

const utf8 = (text) => new TextEncoder().encode(text);

function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}

function equalBytes(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

// ---- canonical.js ---------------------------------------------------
// Canonical JSON for manifests, byte for byte the same as the Python reference:
//   json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
//
// JSON.parse and JSON.stringify cannot do this. They lose the difference between 5 and 5.0,
// write 1e-7 where Python writes 1e-07, and sort keys by UTF-16 unit instead of code point.
// This module parses the text itself, keeps each number's kind, and formats the output
// with Python's rules. test/vectors.test.js replays spec/vectors to prove it.


class CanonicalError extends Error {}

// ---- parsing ----------------------------------------------------------------

const WS = new Set([" ", "\t", "\n", "\r"]);

class Parser {
  constructor(text) {
    this.text = text;
    this.i = 0;
  }

  fail(message) {
    throw new CanonicalError(`${message} at position ${this.i}`);
  }

  skip() {
    while (this.i < this.text.length && WS.has(this.text[this.i])) this.i++;
  }

  parseDocument() {
    this.skip();
    const value = this.value();
    this.skip();
    if (this.i !== this.text.length) this.fail("unexpected text after the JSON value");
    return value;
  }

  value() {
    const c = this.text[this.i];
    if (c === "{") return this.object();
    if (c === "[") return this.array();
    if (c === '"') return { t: "str", v: this.string() };
    if (c === "t" && this.text.startsWith("true", this.i)) { this.i += 4; return { t: "bool", v: true }; }
    if (c === "f" && this.text.startsWith("false", this.i)) { this.i += 5; return { t: "bool", v: false }; }
    if (c === "n" && this.text.startsWith("null", this.i)) { this.i += 4; return { t: "null" }; }
    if (c === "-" || (c >= "0" && c <= "9")) return this.number();
    return this.fail("unexpected character");
  }

  object() {
    this.i++;
    const members = new Map(); // later duplicate keys win, as in Python
    this.skip();
    if (this.text[this.i] === "}") { this.i++; return { t: "obj", v: members }; }
    for (;;) {
      this.skip();
      if (this.text[this.i] !== '"') this.fail("expected a string key");
      const key = this.string();
      this.skip();
      if (this.text[this.i] !== ":") this.fail("expected ':'");
      this.i++;
      this.skip();
      members.set(key, this.value());
      this.skip();
      const c = this.text[this.i++];
      if (c === "}") return { t: "obj", v: members };
      if (c !== ",") { this.i--; this.fail("expected ',' or '}'"); }
    }
  }

  array() {
    this.i++;
    const items = [];
    this.skip();
    if (this.text[this.i] === "]") { this.i++; return { t: "arr", v: items }; }
    for (;;) {
      this.skip();
      items.push(this.value());
      this.skip();
      const c = this.text[this.i++];
      if (c === "]") return { t: "arr", v: items };
      if (c !== ",") { this.i--; this.fail("expected ',' or ']'"); }
    }
  }

  string() {
    this.i++; // opening quote
    let out = "";
    for (;;) {
      if (this.i >= this.text.length) this.fail("unterminated string");
      const c = this.text[this.i++];
      if (c === '"') return out;
      if (c === "\\") {
        const e = this.text[this.i++];
        const simple = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };
        if (e in simple) out += simple[e];
        else if (e === "u") {
          const hex = this.text.slice(this.i, this.i + 4);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) this.fail("bad \\u escape");
          out += String.fromCharCode(parseInt(hex, 16));
          this.i += 4;
        } else this.fail("bad escape");
      } else if (c < " ") {
        this.i--;
        this.fail("control character in string");
      } else out += c;
    }
  }

  number() {
    const match = /^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?/.exec(this.text.slice(this.i));
    if (!match) this.fail("bad number");
    this.i += match[0].length;
    const isInt = match[2] === undefined && match[3] === undefined;
    return isInt ? { t: "int", v: match[0] } : { t: "float", v: match[0] };
  }
}

// ---- number formatting (Python repr rules) ----------------------------------

/** Python's repr(float) for a finite JS number. */
function pythonFloatRepr(x) {
  if (!Number.isFinite(x)) throw new CanonicalError("NaN and infinity are not allowed");
  if (x === 0) return Object.is(x, -0) ? "-0.0" : "0.0";
  const sign = x < 0 ? "-" : "";
  // toExponential() with no argument gives the shortest digits that round-trip.
  const [mantissa, exponent] = Math.abs(x).toExponential().split("e");
  const digits = mantissa.replace(".", "");
  const decpt = Number(exponent) + 1; // position of the decimal point relative to the digits
  if (decpt > 16 || decpt <= -4) {
    const e = decpt - 1;
    const head = digits.length === 1 ? digits : `${digits[0]}.${digits.slice(1)}`;
    return `${sign}${head}e${e < 0 ? "-" : "+"}${String(Math.abs(e)).padStart(2, "0")}`;
  }
  if (decpt <= 0) return `${sign}0.${"0".repeat(-decpt)}${digits}`;
  if (decpt >= digits.length) return `${sign}${digits}${"0".repeat(decpt - digits.length)}.0`;
  return `${sign}${digits.slice(0, decpt)}.${digits.slice(decpt)}`;
}

function formatNumber(node) {
  if (node.t === "int") return node.v === "-0" ? "0" : node.v;
  const value = Number(node.v);
  if (!Number.isFinite(value)) throw new CanonicalError(`number is out of range: ${node.v}`);
  return pythonFloatRepr(value);
}

// ---- serialization ----------------------------------------------------------

function compareCodePoints(a, b) {
  const x = Array.from(a, (c) => c.codePointAt(0));
  const y = Array.from(b, (c) => c.codePointAt(0));
  const n = Math.min(x.length, y.length);
  for (let i = 0; i < n; i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
}


function assertWellFormed(text) {
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    if (c >= 0xd800 && c <= 0xdbff) {
      const d = text.charCodeAt(i + 1);
      if (!(d >= 0xdc00 && d <= 0xdfff)) throw new CanonicalError("lone surrogate in string");
      i++;
    } else if (c >= 0xdc00 && c <= 0xdfff) throw new CanonicalError("lone surrogate in string");
  }
}

function quote(text) {
  assertWellFormed(text);
  let out = '"';
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\f") out += "\\f";
    else if (code < 0x20) out += `\\u${code.toString(16).padStart(4, "0")}`;
    else out += ch;
  }
  return out + '"';
}

function write(node) {
  switch (node.t) {
    case "null": return "null";
    case "bool": return node.v ? "true" : "false";
    case "int":
    case "float": return formatNumber(node);
    case "str": return quote(node.v);
    case "arr": return `[${node.v.map(write).join(",")}]`;
    case "obj": {
      const keys = [...node.v.keys()].sort(compareCodePoints);
      return `{${keys.map((k) => `${quote(k)}:${write(node.v.get(k))}`).join(",")}}`;
    }
    default: throw new CanonicalError("unknown node");
  }
}

/** Canonical text of a JSON document given as text. */
function canonicalizeText(jsonText) {
  return write(new Parser(jsonText).parseDocument());
}

/** Canonical bytes (UTF-8) of a JSON document given as text. */
function canonicalBytes(jsonText) {
  return utf8(canonicalizeText(jsonText));
}

/** SHA-256 of the canonical manifest, as 64 lowercase hex characters. Matches `dotsci-runner hash`. */
function manifestHash(jsonText) {
  return toHex(sha256(canonicalBytes(jsonText)));
}

// ---- merkle.js ------------------------------------------------------
// RFC 6962 Merkle trees over SHA-256 and DotSci's file leaf format.
// Mirrors packages/protocol/src/dotsci_protocol/commit.py.


class CommitError extends Error {}

const LEAF = new Uint8Array([0]);
const NODE = new Uint8Array([1]);

const leafHash = (data) => sha256(concat(LEAF, data));
const nodeHash = (left, right) => sha256(concat(NODE, left, right));

function splitPoint(n) {
  let k = 1;
  while (k * 2 < n) k *= 2;
  return k;
}

/** Merkle tree hash of already prepared leaf data (Uint8Array items). */
function merkleRoot(leaves) {
  const n = leaves.length;
  if (n === 0) return sha256(new Uint8Array(0));
  if (n === 1) return leafHash(leaves[0]);
  const k = splitPoint(n);
  return nodeHash(merkleRoot(leaves.slice(0, k)), merkleRoot(leaves.slice(k)));
}

/** Audit path for the leaf at index. */
function auditPath(leaves, index) {
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
function verifyInclusion(root, size, index, leafData, siblings) {
  if (!Number.isInteger(size) || !Number.isInteger(index) || size < 1 || index < 0 || index >= size) return false;
  const got = rootFromPath(index, size, leafHash(leafData), siblings);
  return got !== null && equalBytes(got, root);
}

// ---- file commitments -------------------------------------------------------

function checkPath(path) {
  const bad = () => { throw new CommitError(`invalid path: ${JSON.stringify(path)}`); };
  if (typeof path !== "string" || path === "" || path.startsWith("/") || path.includes("\\")) bad();
  for (const part of path.split("/")) if (part === "" || part === "." || part === "..") bad();
}

/** uint32_be(len(path)) || path (UTF-8) || sha256(file) */
function fileLeaf(path, sha256Hex) {
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
function commitFiles(hashes) {
  const entries = Object.entries(hashes);
  for (const [path] of entries) checkPath(path);
  const files = entries
    .map(([p, d]) => [p, d.toLowerCase()])
    .sort((a, b) => compareBytes(utf8(a[0]), utf8(b[0])));
  const leaves = files.map(([p, d]) => fileLeaf(p, d));
  return { root: toHex(merkleRoot(leaves)), size: files.length, files, leaves };
}

/** Inclusion proof for one path of a commitment: { path, sha256, index, size, siblings (hex) }. */
function proveFile(commitment, path) {
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
function verifyFileProof(proof, rootHex) {
  try {
    const root = fromHex(rootHex.replace(/^0x/, ""));
    checkPath(proof.path);
    return verifyInclusion(root, proof.size, proof.index, fileLeaf(proof.path, proof.sha256), proof.siblings.map(fromHex));
  } catch {
    return false;
  }
}

// ---- assignment.js --------------------------------------------------
// Verifiable assignment: a pure function of (seed, claim, role, candidates).
// Mirrors packages/protocol/src/dotsci_protocol/assignment.py. Words are BigInt.


class AssignmentError extends Error {}

const DOMAIN = utf8("dotsci/assign/v1");
const WORD_SPACE = 1n << 64n;

function lengthPrefixed(bytes) {
  const prefix = new Uint8Array(4);
  new DataView(prefix.buffer).setUint32(0, bytes.length);
  return concat(prefix, bytes);
}

/** Deterministic stream of unsigned 64 bit words (BigInt). */
class Stream {
  constructor(seed, claimId, role) {
    if (!(seed instanceof Uint8Array) || seed.length < 16) throw new AssignmentError("seed must be at least 16 bytes");
    this.prefix = concat(DOMAIN, lengthPrefixed(seed), lengthPrefixed(utf8(claimId)), lengthPrefixed(utf8(role)));
    this.counter = 0n;
    this.buffer = new Uint8Array(0);
  }

  nextWord() {
    if (this.buffer.length < 8) {
      const counter = new Uint8Array(8);
      new DataView(counter.buffer).setBigUint64(0, this.counter);
      this.counter += 1n;
      this.buffer = concat(this.buffer, sha256(concat(this.prefix, counter)));
    }
    const word = new DataView(this.buffer.buffer, this.buffer.byteOffset, 8).getBigUint64(0);
    this.buffer = this.buffer.slice(8);
    return word;
  }
}

/** Uniform integer in [0, n) by rejection sampling. n and the words are BigInt. */
function uniformBelow(nextWord, n) {
  if (typeof n !== "bigint" || n < 1n) throw new AssignmentError("n must be at least 1");
  const limit = WORD_SPACE - (WORD_SPACE % n);
  for (;;) {
    const word = nextWord();
    if (word < limit) return word % n;
  }
}

/** Pick count distinct candidates for a role on a claim. */
function draw(seed, claimId, role, candidates, count = 1) {
  const pool = [...new Set(candidates)].sort(compareCodePoints);
  if (!Number.isInteger(count) || count < 0) throw new AssignmentError("count cannot be negative");
  if (count > pool.length) throw new AssignmentError(`cannot draw ${count} from ${pool.length} eligible candidates`);
  const stream = new Stream(seed, claimId, role);
  const picks = [];
  for (let i = 0; i < count; i++) {
    const j = i + Number(uniformBelow(() => stream.nextWord(), BigInt(pool.length - i)));
    [pool[i], pool[j]] = [pool[j], pool[i]];
    picks.push(pool[i]);
  }
  return picks;
}

/** True if picks is exactly what the draw produces for these inputs. Never throws. */
function verifyDraw(seed, claimId, role, candidates, picks) {
  try {
    const expected = draw(seed, claimId, role, candidates, picks.length);
    return expected.length === picks.length && expected.every((p, i) => p === picks[i]);
  } catch {
    return false;
  }
}

// ---- settlement.js --------------------------------------------------
// Integer settlement engine in basis points. All amounts are BigInt, so uint256 values are exact.
// Mirrors packages/protocol/src/dotsci_protocol/settlement.py.
// Parameters are required arguments: the real values are open decisions.

const BPS = 10000n;

class SettlementError extends Error {}
class TieError extends SettlementError {}

const PARAM_NAMES = [
  "runner_slash_bps", "challenger_slash_bps", "reviewer_slash_bps", "reviewer_pool_bps",
  "challenger_reward_bps", "confirm_reward_bps", "spec_issue_pay_bps",
];

/** Validate and convert parameters (numbers, strings or BigInt) to BigInt basis points. */
function params(input) {
  const out = {};
  for (const name of PARAM_NAMES) {
    let v;
    try { v = BigInt(input[name]); } catch { throw new SettlementError(`${name} must be an integer between 0 and 10000`); }
    if (v < 0n || v > BPS) throw new SettlementError(`${name} must be an integer between 0 and 10000`);
    out[name] = v;
  }
  return out;
}

const bps = (amount, share) => (amount * share) / BPS; // BigInt division floors for non-negative values

function amountOf(v) {
  let n;
  try { n = BigInt(v); } catch { throw new SettlementError("amounts must be non-negative integers"); }
  if (n < 0n) throw new SettlementError("amounts must be non-negative integers");
  return n;
}

/**
 * Settle one case. case_ fields: kind, bounty, runner, runner_stake, challenger, challenger_stake,
 * reviewer_stakes ({id: amount}), votes ({id: "runner"|"challenger"}). Amounts may be decimal strings.
 * Returns { verdict, payouts: {id: BigInt}, toVault, toTreasury }.
 */
function settle(case_, rawParams) {
  const p = params(rawParams);
  const kind = case_.kind;
  const bounty = amountOf(case_.bounty);
  const runnerStake = amountOf(case_.runner_stake ?? 0);
  const challengerStake = amountOf(case_.challenger_stake ?? 0);
  const stakes = {};
  for (const [id, v] of Object.entries(case_.reviewer_stakes ?? {})) stakes[id] = amountOf(v);
  const votes = case_.votes ?? {};
  const { runner, challenger } = case_;

  if (!["unchallenged", "confirmed", "disputed", "spec_issue"].includes(kind)) throw new SettlementError(`unknown case kind: ${kind}`);
  const named = [runner, challenger, ...Object.keys(stakes)].filter((x) => x !== null && x !== undefined);
  if (new Set(named).size !== named.length) throw new SettlementError("one agent cannot hold more than one role on a claim");
  if ((kind === "confirmed" || kind === "disputed") && (challenger === null || challenger === undefined)) {
    throw new SettlementError(`a ${kind} case needs a challenger`);
  }
  if ((kind === "unchallenged" || kind === "spec_issue") && (challenger || challengerStake)) {
    throw new SettlementError(`a ${kind} case has no challenger`);
  }

  const payouts = {};
  const give = (who, amount) => { payouts[who] = (payouts[who] ?? 0n) + amount; };
  let toVault = 0n;
  let toTreasury = 0n;
  let verdict = "none";

  if (kind === "unchallenged") {
    give(runner, bounty + runnerStake);
  } else if (kind === "spec_issue") {
    const paid = bps(bounty, p.spec_issue_pay_bps);
    give(runner, paid + runnerStake);
    toVault += bounty - paid;
  } else if (kind === "confirmed") {
    const reward = bps(bounty, p.confirm_reward_bps);
    give(challenger, challengerStake + reward);
    give(runner, bounty - reward + runnerStake);
    verdict = "runner";
  } else {
    const ids = Object.keys(stakes);
    if (ids.length === 0) throw new SettlementError("a disputed case needs reviewers");
    const voters = Object.keys(votes);
    if (voters.length !== ids.length || !voters.every((v) => v in stakes)) throw new SettlementError("every reviewer must have voted, and only reviewers can vote");
    if (Object.values(votes).some((v) => v !== "runner" && v !== "challenger")) throw new SettlementError("votes must be 'runner' or 'challenger'");
    const forRunner = voters.filter((r) => votes[r] === "runner");
    const forChallenger = voters.filter((r) => votes[r] === "challenger");
    if (forRunner.length === forChallenger.length) throw new TieError("reviewers are split evenly");
    verdict = forRunner.length > forChallenger.length ? "runner" : "challenger";
    const majority = verdict === "runner" ? forRunner : forChallenger;
    const minority = verdict === "runner" ? forChallenger : forRunner;

    let pool = 0n;
    for (const r of minority) {
      const cut = bps(stakes[r], p.reviewer_slash_bps);
      give(r, stakes[r] - cut);
      pool += cut;
    }
    let winner;
    let winnerBase;
    if (verdict === "runner") {
      const cut = bps(challengerStake, p.challenger_slash_bps);
      give(challenger, challengerStake - cut);
      pool += cut;
      winner = runner;
      winnerBase = bounty + runnerStake;
    } else {
      const cut = bps(runnerStake, p.runner_slash_bps);
      give(runner, runnerStake - cut);
      pool += cut;
      const reward = bps(bounty, p.challenger_reward_bps);
      toVault += bounty - reward;
      winner = challenger;
      winnerBase = challengerStake + reward;
    }
    const reviewersTotal = bps(pool, p.reviewer_pool_bps);
    const each = reviewersTotal / BigInt(majority.length);
    toTreasury += reviewersTotal - each * BigInt(majority.length);
    for (const r of majority) give(r, stakes[r] + each);
    give(winner, winnerBase + (pool - reviewersTotal));
  }

  const totalIn = bounty + runnerStake + challengerStake + Object.values(stakes).reduce((a, b) => a + b, 0n);
  const totalOut = Object.values(payouts).reduce((a, b) => a + b, 0n) + toVault + toTreasury;
  if (totalOut !== totalIn) throw new SettlementError("conservation violated");
  return { verdict, payouts, toVault, toTreasury, totalIn };
}

// ---- dots.js --------------------------------------------------------
// The dots: deterministic agent identities drawn as the DotSci mark, plus the layout
// helper a frontend needs. Everything is a pure function of an id string, so the same
// agent looks the same everywhere, and nothing here is fetched or stored.
//
// The mark is the real logo: six outer dots around a three lobed core, in the 800 by 800
// coordinate space of assets/banner.svg. An identity changes the core's tint and
// rotation, which outer dots are bright, their sizes and pulse timing. It never changes
// the shape, so every agent is recognisably a dot.


const LOGO_CORE_PATH =
  "M710.5 402C710.1 406.2 709.1 411.3 708 415C707 418.7 706.9 419.7 704.2 424C701.6 428.3 695.9 436.7 692 441C688.1 445.3 684.3 447.8 681 450.1C677.7 452.3 675.5 453.3 672 454.7C668.5 456 664.3 457.5 660 458.3C655.7 459.1 651.5 459.8 646 459.5C640.5 459.2 632.8 458.3 627 456.5C621.2 454.7 615.2 451.1 611 448.5C606.8 445.9 606.9 446 602 440.8C597.1 435.5 587.9 422.9 581.4 417C574.9 411.1 569.2 408.1 563 405.3C556.8 402.6 550.7 401.4 544 400.6C537.3 399.8 528.2 400.3 523 400.5C517.8 400.8 517.7 400.6 513 401.9C508.3 403.3 499.9 406.3 495 408.8C490.1 411.3 486.8 414.3 483.6 417C480.4 419.7 480.4 419.1 476 424.8C471.6 430.6 462.7 444.7 457 451.4C451.3 458 446.7 461.3 442 464.7C437.3 468.1 432.8 470.2 429 472C425.2 473.8 423.2 474.5 419 475.6C414.8 476.7 409 477.9 404 478.4C399 478.9 394.7 479 389 478.5C383.3 477.9 376.5 477.2 370 475C363.5 472.9 356.2 469.6 350 465.5C343.8 461.4 338.8 457.2 333 450.4C327.2 443.6 319.3 430.5 315 424.9C310.7 419.2 311 419.8 307 416.7C303 413.6 295.7 408.8 291 406.3C286.3 403.9 282.5 402.9 279 401.9C275.5 401 275.5 400.6 270 400.6C264.5 400.6 253.5 400.3 246 401.9C238.5 403.6 230.9 407.1 225 410.6C219.1 414.1 215.7 417.5 210.6 423C205.4 428.5 198.3 438.9 194 443.4C189.7 447.9 188.2 448.1 185 450.1C181.8 452 179.8 453.5 175 455.1C170.2 456.7 162.8 459.1 156 459.5C149.2 459.8 140.7 459 134 457.4C127.3 455.7 120.5 451.8 116 449.3C111.5 446.8 109.8 445.1 107 442.4C104.2 439.7 102.2 438.2 99.2 433C96.2 427.8 90.9 418.2 88.9 411C87 403.8 87.3 395.7 87.5 390C87.7 384.3 88.9 381.2 90.2 377C91.5 372.8 92.4 369.9 95.5 365C98.6 360.1 105.1 351.7 109 347.6C112.9 343.4 115.3 342.4 119 340.3C122.7 338.2 125.7 336.4 131 334.9C136.3 333.4 145.2 331.8 151 331.5C156.8 331.2 160.7 331.5 166 332.9C171.3 334.3 177.6 336.9 182.7 340C187.9 343.1 191.1 345.6 197 351.5C202.9 357.4 212.5 370.1 218 375.4C223.5 380.8 225.8 381.2 230 383.4C234.2 385.7 237.3 387.5 243 388.8C248.7 390.1 258 391.3 264 391.4C270 391.4 273.3 390.8 279 389.1C284.7 387.4 293.1 383.7 298 381.2C302.9 378.7 305.2 376.9 308.4 374C311.6 371.1 313 369.4 317.1 364C321.2 358.6 327.7 347.8 333 341.6C338.3 335.4 343.8 330.7 349 326.9C354.2 323.1 360 320.6 364 318.8C368 316.9 368.8 316.9 373 315.9C377.2 314.9 384.5 313.3 389 312.7C393.5 312.2 395 312 400 312.5C405 313 412.7 313.7 419 315.7C425.3 317.6 431.8 320 438 324.1C444.2 328.1 450.2 333 456.4 340C462.7 347 470.7 359.9 475.7 366C480.6 372.1 481.3 372.9 486 376.3C490.7 379.7 497.2 384 504 386.5C510.8 389 521.3 390.6 527 391.4C532.7 392.2 533.5 391.8 538 391.4C542.5 391 548.2 390.9 554 389.1C559.8 387.3 568 383.5 573 380.7C578 377.8 579 377.4 584.2 372C589.5 366.6 599.6 353.2 604.6 348C609.6 342.8 610.6 343 614 340.9C617.4 338.8 620 336.9 625 335.3C630 333.8 637.8 331.9 644 331.5C650.2 331.2 656.7 332.1 662 333.2C667.3 334.3 672.2 336.5 676 338.4C679.8 340.2 681.2 340.8 685 344.2C688.8 347.6 695.2 353.4 699 358.9C702.8 364.4 706.2 371.8 708.1 377C710 382.2 710 385.8 710.4 390C710.8 394.2 710.9 397.8 710.5 402Z";

const OUTER_DOTS = [
  [399.5, 147.0], [226.0, 218.5], [572.5, 227.0], [231.5, 564.5], [579.0, 564.5], [399.5, 641.0],
];
const OUTER_RADIUS = 52.5;
const CORE_CENTER = [399.0, 395.0];

const PALETTE = [
  { name: "teal", core: "#57c5d2" },
  { name: "mint", core: "#6fe0b0" },
  { name: "sky", core: "#6cb8ff" },
  { name: "indigo", core: "#8f9bff" },
  { name: "violet", core: "#b58cff" },
  { name: "rose", core: "#ff8fb1" },
  { name: "amber", core: "#ffc46b" },
  { name: "lime", core: "#b6e66b" },
];

const CAPABILITIES = [
  "statistics", "machine-learning", "genomics", "imaging", "simulation", "econometrics", "chemistry", "neuroscience",
];

const SYLLABLE_A = ["ka", "vel", "or", "mi", "tha", "ri", "so", "len", "qui", "ar", "ne", "du", "fi", "zo", "bra", "ix"];
const SYLLABLE_B = ["vo", "ra", "lin", "ta", "mus", "den", "ki", "pha", "ro", "sel", "nyx", "bal", "tor", "mei", "gan", "lo"];

const popcount = (n) => n.toString(2).split("1").length - 1;

/** The identity of a dot, a pure function of its id string. */
function dotIdentity(id) {
  if (typeof id !== "string" || id.length === 0) throw new TypeError("a dot id must be a non-empty string");
  const h = sha256(utf8(`dotsci/dot/v1:${id}`));
  const name = `${SYLLABLE_A[h[0] % 16]}${SYLLABLE_B[h[1] % 16]}`;
  const label = name[0].toUpperCase() + name.slice(1) + "-" + toHex(h.slice(2, 3));
  let lit = h[5] & 63;
  if (popcount(lit) < 2) lit |= 0b001001;
  const first = h[18] % CAPABILITIES.length;
  let second = h[19] % (CAPABILITIES.length - 1);
  if (second >= first) second += 1;
  return {
    id,
    name: label,
    hue: PALETTE[h[3] % PALETTE.length],
    rotation: ((h[4] % 5) - 2) * 6, // degrees, a small tilt from -12 to 12 so lobes never collide with the outer dots
    lit: Array.from({ length: 6 }, (_, i) => ((lit >> i) & 1) === 1),
    scales: Array.from({ length: 6 }, (_, i) => 0.82 + (h[6 + i] % 19) / 100), // 0.82 to 1.00
    phases: Array.from({ length: 6 }, (_, i) => (h[12 + i] % 40) / 10), // seconds
    capabilities: [CAPABILITIES[first], CAPABILITIES[second]],
    fingerprint: toHex(h.slice(0, 4)),
  };
}

const STATES = {
  idle: { dots: "#ffffff", pulse: 4.2, core: 0.9 },
  running: { dots: "#ffffff", pulse: 1.4, core: 1.0 },
  challenging: { dots: "#ffc46b", pulse: 1.1, core: 0.95 },
  reviewing: { dots: "#b58cff", pulse: 1.8, core: 0.95 },
};

const escapeXml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[c]);

/**
 * The dot as an SVG string. Options: size (px, default 120), state (idle, running,
 * challenging, reviewing), animate (default true), background (css colour or null).
 */
function renderDot(identity, { size = 120, state = "idle", animate = true, background = null } = {}) {
  const style = STATES[state];
  if (!style) throw new RangeError(`unknown state: ${state}`);
  const uid = identity.fingerprint;
  const [cx, cy] = CORE_CENTER;
  const bg = background ? `<rect x="60" y="60" width="680" height="680" rx="120" fill="${escapeXml(background)}"/>` : "";
  const glow = animate
    ? `<animate attributeName="opacity" values="0.18;0.5;0.18" dur="${(style.pulse * 1.6).toFixed(2)}s" repeatCount="indefinite"/>`
    : "";
  const dots = OUTER_DOTS.map(([x, y], i) => {
    const r = (OUTER_RADIUS * identity.scales[i]).toFixed(1);
    const base = identity.lit[i] ? 1 : 0.35;
    const low = identity.lit[i] ? 0.55 : 0.2;
    const pulse = animate
      ? `<animate attributeName="opacity" values="${base};${low};${base}" dur="${(style.pulse + i * 0.17).toFixed(2)}s" begin="${identity.phases[i].toFixed(1)}s" repeatCount="indefinite"/>`
      : "";
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="${style.dots}" opacity="${base}">${pulse}</circle>`;
  }).join("");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="60 60 680 680" width="${size}" height="${size}" role="img" aria-label="${escapeXml(identity.name)}">` +
    `<defs><filter id="g${uid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="22"/></filter></defs>` +
    bg +
    `<g transform="rotate(${identity.rotation} ${cx} ${cy})">` +
    `<path d="${LOGO_CORE_PATH}" fill="${identity.hue.core}" filter="url(#g${uid})" opacity="0.3">${glow}</path>` +
    `<path d="${LOGO_CORE_PATH}" fill="${identity.hue.core}" opacity="${style.core}"/>` +
    `</g>${dots}</svg>`
  );
}

/** Position of agent i of n on a golden angle spiral inside a width by height box. */
function agentPosition(i, n, width = 1000, height = 600, margin = 48) {
  if (!Number.isInteger(i) || !Number.isInteger(n) || n < 1 || i < 0 || i >= n) throw new RangeError("bad index");
  const golden = Math.PI * (3 - Math.sqrt(5));
  const radius = Math.sqrt((i + 0.5) / n);
  const angle = i * golden;
  const rx = width / 2 - margin;
  const ry = height / 2 - margin;
  return { x: width / 2 + Math.cos(angle) * radius * rx, y: height / 2 + Math.sin(angle) * radius * ry };
}

// ---- colony.js ------------------------------------------------------
// A deterministic colony: dots (agents) listing claims, drawing runners and reviewer
// panels, rerunning, challenging and settling, entirely from a seed.
//
// THIS IS A SIMULATION. It runs the real assignment (draw) and settlement (settle) code
// from this package, so every draw can be re-verified and money is conserved, but the
// agents, claims, results and odds are generated. It is for demonstration and for trying
// the rules, never a record of real activity. The honesty and challenge probabilities
// below are made up to produce a lively world, not measured from anything.


// Illustrative parameters. The protocol's real values are open decisions.
const DEFAULT_PARAMS = {
  runner_slash_bps: 5000, challenger_slash_bps: 3000, reviewer_slash_bps: 2000, reviewer_pool_bps: 4000,
  challenger_reward_bps: 2500, confirm_reward_bps: 500, spec_issue_pay_bps: 1000,
};

// Made up odds, out of 100.
const ODDS = {
  claimReproduces: 70, runnerHonest: 92, specIssue: 4, catchWrong: 90, confirm: 25, falseChallenge: 6, reviewerCorrect: 85,
};

const STUDY_TITLES = {
  statistics: "Effect size rerun", "machine-learning": "Benchmark score rerun", genomics: "Expression result rerun",
  imaging: "Segmentation metric rerun", simulation: "Simulation output rerun", econometrics: "Regression estimate rerun",
  chemistry: "Yield figure rerun", neuroscience: "Spike rate rerun",
};

class Rand {
  constructor(seedBytes, label) {
    this.stream = new Stream(seedBytes, "colony", label);
  }

  below(n) {
    return Number(uniformBelow(() => this.stream.nextWord(), BigInt(n)));
  }

  between(lo, hi) {
    return lo + this.below(hi - lo + 1);
  }

  chance(percent) {
    return this.below(100) < percent;
  }
}

const str = (n) => n.toString();

/**
 * Run a colony. Options: seed (any string), agents (6 to 200), claims (1 to 200), params.
 * Returns plain data, amounts as decimal strings, safe to JSON.stringify.
 */
function runColony({ seed = "dotsci", agents: agentCount = 24, claims: claimCount = 12, params = DEFAULT_PARAMS } = {}) {
  if (!Number.isInteger(agentCount) || agentCount < 6 || agentCount > 200) throw new RangeError("agents must be an integer from 6 to 200");
  if (!Number.isInteger(claimCount) || claimCount < 1 || claimCount > 200) throw new RangeError("claims must be an integer from 1 to 200");
  const seedText = String(seed);
  const seedBytes = sha256(utf8(`dotsci/colony/v1:${seedText}`));

  const opRand = new Rand(seedBytes, "operators");
  const operatorCount = Math.max(2, Math.ceil(agentCount / 3));
  const START = 10_000n;
  const agents = Array.from({ length: agentCount }, (_, i) => {
    const id = `dot_${toHex(sha256(utf8(`${seedText}:agent:${i}`))).slice(0, 8)}`;
    return {
      id, index: i, operator: `op-${opRand.below(operatorCount) + 1}`, identity: dotIdentity(id), balance: START,
      stats: { runs: 0, reproduced: 0, notReproduced: 0, challenges: 0, panels: 0, won: 0, lost: 0, specIssues: 0 },
    };
  });
  const byId = new Map(agents.map((a) => [a.id, a]));
  const present = [...new Set(agents.flatMap((a) => a.identity.capabilities))].sort();

  const claimRand = new Rand(seedBytes, "claims");
  const claims = Array.from({ length: claimCount }, (_, j) => {
    const capability = present[claimRand.below(present.length)];
    const bounty = BigInt(500 + 100 * claimRand.below(46));
    return {
      id: `claim-${j + 1}`, capability, bounty, runnerStake: bounty / 10n, challengerStake: bounty / 10n,
      reviewerStake: bounty / 20n, submitter: agents[claimRand.below(agentCount)].id,
      code: toHex(sha256(utf8(`${seedText}:claim:${j}`))).slice(0, 4), truth: claimRand.chance(ODDS.claimReproduces),
    };
  });

  let vault = claims.reduce((a, c) => a + c.bounty, 0n);
  let treasury = 0n;
  const totalStart = agents.reduce((a, x) => a + x.balance, 0n) + vault;

  const events = [];
  const claimResults = [];
  const sim = new Rand(seedBytes, "lifecycle");
  const canAfford = (a, stake) => a.balance >= stake;

  claims.forEach((claim, j) => {
    let t = j * 900 + sim.between(0, 300);
    const emit = (type, agentIds, data = {}) => {
      events.push({ id: `${claim.id}:${events.filter((e) => e.claim === claim.id).length}`, t, claim: claim.id, type, agents: agentIds, data });
    };
    const submitter = byId.get(claim.submitter);
    const title = `${STUDY_TITLES[claim.capability]} (synthetic ${claim.code})`;
    emit("claim_listed", [submitter.id], { title, capability: claim.capability, bounty: str(claim.bounty), simulated: true });

    // Runner: drawn at random from the eligible pool.
    t += sim.between(30, 120);
    const runnerPool = agents
      .filter((a) => a.identity.capabilities.includes(claim.capability) && a.operator !== submitter.operator && canAfford(a, claim.runnerStake))
      .map((a) => a.id)
      .sort();
    if (runnerPool.length === 0) {
      emit("claim_unassigned", [submitter.id], { reason: "no eligible runner" });
      claimResults.push({ id: claim.id, title, capability: claim.capability, bounty: str(claim.bounty), submitter: submitter.id, status: "unassigned" });
      return;
    }
    const runnerId = draw(seedBytes, claim.id, "runner", runnerPool, 1)[0];
    const runner = byId.get(runnerId);
    emit("runner_assigned", [runnerId], { role: "runner", candidates: runnerPool, pick: runnerId, stake: str(claim.runnerStake) });
    runner.stats.runs += 1;

    t += sim.between(600, 1800);
    const specIssue = sim.chance(ODDS.specIssue);
    const honest = sim.chance(ODDS.runnerHonest);
    const reported = honest ? claim.truth : !claim.truth;
    const outcome = specIssue ? "spec_issue" : reported ? "reproduced" : "not_reproduced";
    emit("run_completed", [runnerId], { outcome });

    let kind = "unchallenged";
    let challenger = null;
    if (specIssue) kind = "spec_issue";
    else {
      t += 3600;
      let challenges = false;
      let confirms = false;
      if (reported !== claim.truth) challenges = sim.chance(ODDS.catchWrong);
      else if (sim.chance(ODDS.falseChallenge)) challenges = true;
      else if (sim.chance(ODDS.confirm)) confirms = true;
      if (challenges || confirms) {
        const pool = agents
          .filter((a) => a.id !== runnerId && a.operator !== runner.operator && canAfford(a, claim.challengerStake))
          .map((a) => a.id)
          .sort();
        if (pool.length > 0) {
          challenger = byId.get(draw(seedBytes, claim.id, "challenger", pool, 1)[0]);
          kind = challenges ? "disputed" : "confirmed";
        }
      }
    }

    let reviewerStakes = {};
    let votes = {};
    let panel = [];
    if (challenger) {
      challenger.stats.challenges += 1;
      emit(kind === "disputed" ? "challenged" : "confirmed", [challenger.id], { stake: str(claim.challengerStake) });
    }
    if (kind === "disputed") {
      t += 60;
      const blocked = new Set([runner.operator, challenger.operator, submitter.operator]);
      const pool = agents
        .filter((a) => a.id !== runnerId && a.id !== challenger.id && !blocked.has(a.operator) && canAfford(a, claim.reviewerStake))
        .map((a) => a.id)
        .sort();
      let size = sim.chance(30) ? 5 : 3;
      while (size > pool.length) size -= 2;
      if (size < 1) {
        kind = "spec_issue"; // no independent panel can be drawn, so the claim is relisted
        emit("dispute_unresolved", [challenger.id], { reason: "not enough independent reviewers" });
      } else {
        panel = draw(seedBytes, claim.id, "reviewer", pool, size);
        emit("panel_drawn", panel, { role: "reviewer", candidates: pool, picks: panel, stake: str(claim.reviewerStake) });
        const challengerRight = reported !== claim.truth;
        for (const id of panel) {
          t += sim.between(60, 400);
          const correct = sim.chance(ODDS.reviewerCorrect);
          const side = correct === challengerRight ? "challenger" : "runner";
          votes[id] = side;
          reviewerStakes[id] = claim.reviewerStake;
          byId.get(id).stats.panels += 1;
          emit("vote", [id], { vote: side });
        }
      }
    }

    // Money moves only through the real settlement engine.
    const isDispute = kind === "disputed";
    const settleCase = {
      kind, bounty: claim.bounty, runner: runnerId, runner_stake: claim.runnerStake,
      challenger: kind === "disputed" || kind === "confirmed" ? challenger.id : null,
      challenger_stake: kind === "disputed" || kind === "confirmed" ? claim.challengerStake : 0n,
      reviewer_stakes: isDispute ? reviewerStakes : {}, votes: isDispute ? votes : {},
    };
    const before = new Map(agents.map((a) => [a.id, a.balance]));
    const staked = [[runner, claim.runnerStake]];
    if (settleCase.challenger) staked.push([byId.get(settleCase.challenger), claim.challengerStake]);
    if (isDispute) for (const id of panel) staked.push([byId.get(id), claim.reviewerStake]);
    for (const [a, stake] of staked) a.balance -= stake;
    vault -= claim.bounty;
    const result = settle(settleCase, params);
    for (const [id, amount] of Object.entries(result.payouts)) byId.get(id).balance += amount;
    vault += result.toVault;
    treasury += result.toTreasury;

    t += sim.between(60, 300);
    const net = {};
    for (const id of Object.keys(result.payouts)) net[id] = str(byId.get(id).balance - before.get(id));
    emit("settled", Object.keys(result.payouts), {
      kind, verdict: result.verdict, payouts: Object.fromEntries(Object.entries(result.payouts).map(([k, v]) => [k, str(v)])),
      net, to_vault: str(result.toVault), to_treasury: str(result.toTreasury), outcome,
    });

    if (kind === "spec_issue") runner.stats.specIssues += 1;
    else if (outcome === "reproduced") runner.stats.reproduced += 1;
    else runner.stats.notReproduced += 1;
    if (kind === "disputed" || kind === "confirmed") {
      const runnerWon = result.verdict === "runner";
      byId.get(runnerId).stats[runnerWon ? "won" : "lost"] += 1;
      challenger.stats[runnerWon ? "lost" : "won"] += 1;
    }
    claimResults.push({
      id: claim.id, title, capability: claim.capability, bounty: str(claim.bounty), submitter: submitter.id, runner: runnerId,
      challenger: challenger ? challenger.id : null, panel, kind, outcome, verdict: result.verdict, status: "settled",
    });
  });

  events.sort((a, b) => a.t - b.t || (a.id < b.id ? -1 : 1));
  const totalEnd = agents.reduce((a, x) => a + x.balance, 0n) + vault + treasury;
  return {
    simulated: true,
    seed: seedText,
    seedHex: toHex(seedBytes),
    params,
    agents: agents.map((a) => ({
      id: a.id, index: a.index, operator: a.operator, identity: a.identity, balance: str(a.balance),
      net: str(a.balance - START), stats: a.stats,
    })),
    claims: claimResults,
    events,
    vault: str(vault),
    treasury: str(treasury),
    invariant: { start: str(totalStart), end: str(totalEnd), holds: totalStart === totalEnd },
  };
}

/** Agents ranked by net change in balance, then id. Simulated numbers. */
function leaderboard(colony) {
  return [...colony.agents]
    .sort((a, b) => (BigInt(b.net) > BigInt(a.net) ? 1 : BigInt(b.net) < BigInt(a.net) ? -1 : a.id < b.id ? -1 : 1));
}

/**
 * Net change in balance per agent as of event index upToEvent (-1 for the start), so a
 * replay can show standings that grow as events play instead of the final result.
 */
function netAt(colony, upToEvent) {
  const net = Object.fromEntries(colony.agents.map((a) => [a.id, 0n]));
  for (const e of colony.events.slice(0, upToEvent + 1)) {
    if (e.type !== "settled") continue;
    for (const [id, v] of Object.entries(e.data.net)) net[id] += BigInt(v);
  }
  return Object.fromEntries(Object.entries(net).map(([k, v]) => [k, v.toString()]));
}

/** The dot state to draw for an agent at event index i: what it is doing right now. */
function dotStateAt(colony, agentId, upToEvent) {
  const e = colony.events.slice(0, upToEvent + 1).reverse().find((x) => x.agents.includes(agentId));
  if (!e) return "idle";
  if (e.type === "runner_assigned") return "running";
  if (e.type === "challenged" || e.type === "confirmed") return "challenging";
  if (e.type === "panel_drawn" || e.type === "vote") return "reviewing";
  return "idle";
}

export { AssignmentError, BPS, CAPABILITIES, CORE_CENTER, CanonicalError, CommitError, DEFAULT_PARAMS, LOGO_CORE_PATH, ODDS, OUTER_DOTS, OUTER_RADIUS, PALETTE, STATES, SettlementError, Stream, TieError, agentPosition, auditPath, canonicalBytes, canonicalizeText, checkPath, commitFiles, concat, dotIdentity, dotStateAt, draw, equalBytes, fileLeaf, fromHex, leaderboard, leafHash, manifestHash, merkleRoot, netAt, nodeHash, params, proveFile, pythonFloatRepr, renderDot, runColony, settle, sha256, toHex, uniformBelow, utf8, verifyDraw, verifyFileProof, verifyInclusion };

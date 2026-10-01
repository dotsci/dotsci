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

export { AssignmentError, BPS, CanonicalError, CommitError, SettlementError, Stream, TieError, auditPath, canonicalBytes, canonicalizeText, checkPath, commitFiles, concat, draw, equalBytes, fileLeaf, fromHex, leafHash, manifestHash, merkleRoot, nodeHash, params, proveFile, pythonFloatRepr, settle, sha256, toHex, uniformBelow, utf8, verifyDraw, verifyFileProof, verifyInclusion };

// Verifiable assignment: a pure function of (seed, claim, role, candidates).
// Mirrors packages/protocol/src/dotsci_protocol/assignment.py. Words are BigInt.

import { sha256, concat, utf8 } from "./sha256.js";
import { compareCodePoints } from "./canonical.js";

export class AssignmentError extends Error {}

const DOMAIN = utf8("dotsci/assign/v1");
const WORD_SPACE = 1n << 64n;

function lengthPrefixed(bytes) {
  const prefix = new Uint8Array(4);
  new DataView(prefix.buffer).setUint32(0, bytes.length);
  return concat(prefix, bytes);
}

/** Deterministic stream of unsigned 64 bit words (BigInt). */
export class Stream {
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
export function uniformBelow(nextWord, n) {
  if (typeof n !== "bigint" || n < 1n) throw new AssignmentError("n must be at least 1");
  const limit = WORD_SPACE - (WORD_SPACE % n);
  for (;;) {
    const word = nextWord();
    if (word < limit) return word % n;
  }
}

/** Pick count distinct candidates for a role on a claim. */
export function draw(seed, claimId, role, candidates, count = 1) {
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
export function verifyDraw(seed, claimId, role, candidates, picks) {
  try {
    const expected = draw(seed, claimId, role, candidates, picks.length);
    return expected.length === picks.length && expected.every((p, i) => p === picks[i]);
  } catch {
    return false;
  }
}

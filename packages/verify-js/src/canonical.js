// Canonical JSON for manifests, byte for byte the same as the Python reference:
//   json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
//
// JSON.parse and JSON.stringify cannot do this. They lose the difference between 5 and 5.0,
// write 1e-7 where Python writes 1e-07, and sort keys by UTF-16 unit instead of code point.
// This module parses the text itself, keeps each number's kind, and formats the output
// with Python's rules. test/vectors.test.js replays spec/vectors to prove it.

import { sha256, toHex, utf8 } from "./sha256.js";

export class CanonicalError extends Error {}

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
export function pythonFloatRepr(x) {
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

export { compareCodePoints };

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
export function canonicalizeText(jsonText) {
  return write(new Parser(jsonText).parseDocument());
}

/** Canonical bytes (UTF-8) of a JSON document given as text. */
export function canonicalBytes(jsonText) {
  return utf8(canonicalizeText(jsonText));
}

/** SHA-256 of the canonical manifest, as 64 lowercase hex characters. Matches `dotsci-runner hash`. */
export function manifestHash(jsonText) {
  return toHex(sha256(canonicalBytes(jsonText)));
}

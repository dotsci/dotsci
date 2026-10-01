import test from "node:test";
import assert from "node:assert/strict";
import { canonicalizeText, manifestHash, pythonFloatRepr, CanonicalError } from "../src/index.js";

test("python float repr rules", () => {
  const cases = new Map([
    [0.1, "0.1"], [5, "5.0"], [1e-7, "1e-07"], [1e22, "1e+22"], [1e16, "1e+16"], [1e15, "1000000000000000.0"],
    [0.0001, "0.0001"], [0.00001, "1e-05"], [123456789.123456789, "123456789.12345679"],
    [-2.5, "-2.5"], [5e-324, "5e-324"], [1.7976931348623157e308, "1.7976931348623157e+308"],
    [0.30000000000000004, "0.30000000000000004"], [100, "100.0"], [1234567, "1234567.0"],
  ]);
  for (const [value, expected] of cases) assert.equal(pythonFloatRepr(value), expected, String(value));
  assert.equal(pythonFloatRepr(-0), "-0.0"); // a Map key would hide the sign, so check it directly
  assert.equal(pythonFloatRepr(0), "0.0");
  assert.throws(() => pythonFloatRepr(Infinity), CanonicalError);
  assert.throws(() => pythonFloatRepr(NaN), CanonicalError);
});

test("integers and floats are different tokens", () => {
  assert.equal(canonicalizeText('{"a":5,"b":5.0}'), '{"a":5,"b":5.0}');
  assert.notEqual(manifestHash('{"a":5}'), manifestHash('{"a":5.0}'));
});

test("key order and whitespace do not matter", () => {
  assert.equal(manifestHash('{ "b": 1, "a": {"d":[3,2,1],"c":null} }'), manifestHash('{"a":{"c":null,"d":[3,2,1]},"b":1}'));
});

test("keys sort by code point, not UTF-16 unit", () => {
  assert.equal(canonicalizeText('{"\\ud83d\\ude00":1,"\\uffff":2}'), '{"￿":2,"\u{1f600}":1}');
});

test("duplicate keys: the last one wins", () => {
  assert.equal(canonicalizeText('{"a":1,"a":2}'), '{"a":2}');
});

test("large integers keep every digit", () => {
  assert.equal(canonicalizeText("[123456789012345678901234567890]"), "[123456789012345678901234567890]");
});

test("malformed or unsupported input is rejected", () => {
  for (const bad of ['{"a":1,}', "[1,]", "NaN", "01", "1.", ".5", "+1", '{"a"}', '"\\ud800"', '"abc', "[1 2]", "1e999", "", "{} x", '"\t"']) {
    assert.throws(() => canonicalizeText(bad), CanonicalError, JSON.stringify(bad));
  }
});

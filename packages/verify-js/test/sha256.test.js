import test from "node:test";
import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import { sha256, toHex } from "../src/index.js";

const reference = (bytes) => createHash("sha256").update(bytes).digest("hex");

test("known vectors", () => {
  assert.equal(toHex(sha256(new Uint8Array(0))), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  assert.equal(toHex(sha256(new TextEncoder().encode("abc"))), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
});

test("matches node crypto for every length around block boundaries", () => {
  for (let n = 0; n <= 300; n++) {
    const data = randomBytes(n);
    assert.equal(toHex(sha256(data)), reference(data), `length ${n}`);
  }
});

test("matches node crypto on larger inputs", () => {
  for (const n of [1000, 4096, 65537, 1_000_003]) {
    const data = randomBytes(n);
    assert.equal(toHex(sha256(data)), reference(data), `length ${n}`);
  }
});

test("rejects non byte input", () => {
  assert.throws(() => sha256("abc"), TypeError);
});

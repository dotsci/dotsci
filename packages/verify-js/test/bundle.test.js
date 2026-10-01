import test from "node:test";
import assert from "node:assert/strict";
import * as src from "../src/index.js";
import * as bundle from "../dist/dotsci-verify.mjs";

test("the bundle exports every name the source index exports", () => {
  assert.deepEqual(Object.keys(bundle).sort(), Object.keys(src).filter((k) => k !== "compareCodePoints").sort());
});

test("the bundle behaves exactly like the source", () => {
  const digest = (lib, obj) => lib.toHex(lib.sha256(lib.utf8(JSON.stringify(obj))));
  const options = { seed: "bundle-check", agents: 30, claims: 20 };
  assert.equal(digest(bundle, bundle.runColony(options)), digest(src, src.runColony(options)));
  const id = "dot_bundle";
  assert.equal(bundle.renderDot(bundle.dotIdentity(id)), src.renderDot(src.dotIdentity(id)));
  assert.equal(bundle.manifestHash('{"b":5.0,"a":1e-7}'), src.manifestHash('{"b":5.0,"a":1e-7}'));
});

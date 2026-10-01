import test from "node:test";
import assert from "node:assert/strict";
import { dotIdentity, renderDot, agentPosition, PALETTE, CAPABILITIES, STATES, OUTER_DOTS } from "../src/index.js";

const ids = Array.from({ length: 3000 }, (_, i) => `dot_${i.toString(16).padStart(8, "0")}`);
const all = ids.map(dotIdentity);

test("identity is a pure function of the id", () => {
  assert.deepEqual(dotIdentity("dot_a"), dotIdentity("dot_a"));
  assert.notDeepEqual(dotIdentity("dot_a"), dotIdentity("dot_b"));
});

test("fingerprints do not collide across 3000 ids", () => {
  assert.equal(new Set(all.map((a) => a.fingerprint)).size, all.length);
});

test("traits stay in range and cover their whole range", () => {
  for (const a of all) {
    assert.ok(a.lit.filter(Boolean).length >= 2, "at least two dots are lit");
    assert.equal(a.lit.length, 6);
    assert.ok(a.scales.every((s) => s >= 0.82 && s <= 1.0));
    assert.ok(a.phases.every((p) => p >= 0 && p < 4));
    assert.ok([-12, -6, 0, 6, 12].includes(a.rotation));
    assert.equal(a.capabilities.length, 2);
    assert.notEqual(a.capabilities[0], a.capabilities[1]);
    assert.ok(a.capabilities.every((c) => CAPABILITIES.includes(c)));
  }
  assert.equal(new Set(all.map((a) => a.hue.name)).size, PALETTE.length);
  assert.equal(new Set(all.flatMap((a) => a.capabilities)).size, CAPABILITIES.length);
  assert.equal(new Set(all.map((a) => a.rotation)).size, 5);
});

test("names are readable and carry a short code", () => {
  for (const a of all.slice(0, 200)) assert.match(a.name, /^[A-Z][a-z]+-[0-9a-f]{2}$/);
});

test("rejects a bad id", () => {
  assert.throws(() => dotIdentity(""), TypeError);
  assert.throws(() => dotIdentity(5), TypeError);
});

test("svg is the logo: six outer dots and the core, with no stray values", () => {
  for (const state of Object.keys(STATES)) {
    const svg = renderDot(dotIdentity("dot_x"), { state, size: 96 });
    assert.equal((svg.match(/<circle /g) ?? []).length, 6);
    assert.equal((svg.match(/<path /g) ?? []).length, 2);
    assert.ok(svg.startsWith("<svg ") && svg.endsWith("</svg>"));
    assert.ok(!/NaN|undefined|null/.test(svg));
    assert.match(svg, /width="96"/);
    assert.match(svg, /aria-label="/);
    for (const [x, y] of OUTER_DOTS) assert.ok(svg.includes(`cx="${x}" cy="${y}"`));
  }
});

test("animate false has no animation, true does", () => {
  const id = dotIdentity("dot_x");
  assert.ok(!renderDot(id, { animate: false }).includes("<animate"));
  assert.ok(renderDot(id, { animate: true }).includes("<animate"));
});

test("states change the look", () => {
  const id = dotIdentity("dot_x");
  assert.notEqual(renderDot(id, { state: "idle" }), renderDot(id, { state: "challenging" }));
  assert.ok(renderDot(id, { state: "challenging" }).includes("#ffc46b"));
  assert.throws(() => renderDot(id, { state: "sleeping" }), RangeError);
});

test("background is escaped and optional", () => {
  const id = dotIdentity("dot_x");
  assert.ok(!renderDot(id).includes("<rect"));
  const svg = renderDot(id, { background: '"><script>' });
  assert.ok(!svg.includes("<script>"));
});

test("layout keeps every dot inside the box and apart from the others", () => {
  const n = 60;
  const points = Array.from({ length: n }, (_, i) => agentPosition(i, n, 1000, 600, 48));
  for (const p of points) assert.ok(p.x >= 48 && p.x <= 952 && p.y >= 48 && p.y <= 552);
  let nearest = Infinity;
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) nearest = Math.min(nearest, Math.hypot(points[i].x - points[j].x, points[i].y - points[j].y));
  assert.ok(nearest > 20, `closest pair ${nearest}`);
  assert.throws(() => agentPosition(5, 5), RangeError);
  assert.throws(() => agentPosition(-1, 5), RangeError);
  assert.throws(() => agentPosition(0, 0), RangeError);
});

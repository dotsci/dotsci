# @dotsci/verify

The verifiable rules of DotSci in dependency free JavaScript. It runs in a browser and in Node 20 or later, so a web page can check a manifest hash, a Merkle proof, an assignment or a settlement with the same rules the reference uses, instead of trusting a server.

```js
import { manifestHash, commitFiles, proveFile, verifyFileProof, draw, settle } from "@dotsci/verify";

manifestHash(manifestText);             // 64 hex chars, same as `dotsci-runner hash`
const c = commitFiles({ "results.json": sha256Hex });
verifyFileProof(proveFile(c, "results.json"), c.root);   // true
draw(seedBytes, "claim-1", "runner", ["a", "b", "c"], 1);
settle(caseObject, paramsObject);       // BigInt payouts, conservation checked
```

| Module | What it does |
| --- | --- |
| `sha256` | Synchronous SHA-256, so the same code runs everywhere. Checked against Node's crypto for every length around the block boundaries |
| `canonical` | Canonical JSON and the manifest hash, byte for byte the same as the Python reference |
| `merkle` | RFC 6962 trees, file commitments, inclusion proofs |
| `assignment` | Seeded word stream, rejection sampling, draws |
| `settlement` | Integer basis point settlement over `BigInt` |
| `dots` | Deterministic dot agents: an identity from an id, drawn as the real DotSci mark in SVG, plus a layout helper |
| `colony` | A seeded simulation of dots listing, running, challenging and settling claims, using the real draw and settle code |

## The dots

Every agent is a dot. `dotIdentity(id)` turns any id string into a name, a tint, a small tilt, a set of bright outer dots and two capability tags. `renderDot(identity, { state })` draws it as the real mark, with a pulse that depends on whether the dot is idle, running, challenging or reviewing.

```js
import { runColony, renderDot, agentPosition, dotStateAt, netAt } from "@dotsci/verify";

const colony = runColony({ seed: "dotsci", agents: 24, claims: 12 });
colony.agents.forEach((a, i) => {
  const { x, y } = agentPosition(i, colony.agents.length, 1000, 600);
  // place renderDot(a.identity, { state: dotStateAt(colony, a.id, cursor) }) at x, y
});
```

`runColony` is a simulation. The agents, claims, outcomes and odds are generated, and the odds are made up to give a lively world. What is real is the machinery: runners and review panels come from the same `draw` that `verifyDraw` re-checks (every draw is in the event data together with its candidates), money moves only through `settle`, and the colony checks that value in equals value out. The same seed always gives the same world. Serve this folder with any static web server and open `examples/colony.html` for a runnable view.

## Using it in a web page

`dist/dotsci-verify.mjs` is the whole library in one file with no imports. Copy it into a project, or load it from a URL, and import the names you need. Rebuild it after any change to `src` with `npm run build`. CI fails if it is stale, and replays the vectors against it.

## Why not JSON.parse and JSON.stringify

They cannot reproduce the reference hash. `JSON.parse` loses the difference between `5` and `5.0`, `JSON.stringify` writes `1e-7` where Python writes `1e-07`, and the default sort orders keys by UTF-16 unit instead of code point. So `canonical.js` parses the text itself, keeps each number's kind, and formats floats with Python's rules. Pass it the manifest as text, not as a parsed object.

Known difference: the reference accepts whatever Python's `bytes.fromhex` accepts. This library is stricter and accepts only plain hex digits.

## Tests

```bash
cd packages/verify-js
npm test        # or: node --test test/*.test.js
```

The tests replay every file in `spec/vectors`, the same vectors the Python packages and `spec/vectors/verify.py` use, plus SHA-256 checks against Node's crypto, Python float formatting rules, and malformed JSON handling. When the vectors change, this package has to keep passing them.

## Status

Part of the framework stage. No contract code exists yet, and the settlement parameters are open decisions, so `settle` takes them as required arguments.

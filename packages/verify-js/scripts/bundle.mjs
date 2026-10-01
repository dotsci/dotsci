// Builds dist/dotsci-verify.mjs, one file with no imports, for pasting into a web project
// or loading from a URL. No dependencies. `--check` fails if the file is out of date.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const order = ["sha256", "canonical", "merkle", "assignment", "settlement", "dots", "colony"];
const exported = new Set();
let body = "";

for (const name of order) {
  let text = readFileSync(join(root, "src", `${name}.js`), "utf8");
  text = text.replace(/^import [^;]*;\n/gm, "");
  text = text.replace(/^export \{[^}]*\}( from "[^"]*")?;\n/gm, "");
  text = text.replace(/^export (async function|function|class|const|let) ([A-Za-z0-9_]+)/gm, (_, kind, id) => {
    exported.add(id);
    return `${kind} ${id}`;
  });
  body += `// ---- ${name}.js ${"-".repeat(60 - name.length)}\n${text.trim()}\n\n`;
}

const output =
  "// DotSci verification library, single file build of packages/verify-js/src. Do not edit by hand.\n" +
  "// Rebuild with: node scripts/bundle.mjs\n\n" +
  body +
  `export { ${[...exported].sort().join(", ")} };\n`;

const target = join(root, "dist", "dotsci-verify.mjs");
if (process.argv.includes("--check")) {
  if (!existsSync(target) || readFileSync(target, "utf8") !== output) {
    console.error("dist/dotsci-verify.mjs is out of date, run: node scripts/bundle.mjs");
    process.exit(1);
  }
  console.log("bundle is up to date");
} else {
  writeFileSync(target, output);
  console.log(`wrote dist/dotsci-verify.mjs (${output.length} bytes, ${exported.size} exports)`);
}

// Copies the MathLive and Excalidraw font files out of node_modules into
// public/, where Next serves them from our origin. Both libraries would
// otherwise fetch fonts from a CDN, and a child's browser must not call third
// parties. Runs on postinstall (dev checkout), predev and prebuild (Docker
// images), so the copy is never stale. Output directories are git-ignored.
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const jobs = [
  { from: "node_modules/mathlive/fonts", to: "public/mathlive/fonts" },
  { from: "node_modules/@excalidraw/excalidraw/dist/prod/fonts", to: "public/excalidraw/fonts" },
];

for (const { from, to } of jobs) {
  const source = join(root, from);
  const target = join(root, to);
  if (!existsSync(source)) {
    console.error(`copy-editor-assets: ${from} is missing - run npm install first`);
    process.exit(1);
  }
  rmSync(target, { recursive: true, force: true });
  mkdirSync(dirname(target), { recursive: true });
  cpSync(source, target, { recursive: true });
  console.log(`copy-editor-assets: ${from} -> ${to}`);
}

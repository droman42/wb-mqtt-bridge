#!/usr/bin/env node
/**
 * Orphan guard — fail if any source module is unreachable from the app entry points.
 *
 * The strict ESLint gate (`--max-warnings 0`) only flags unused *locals/imports within a file*; it cannot see an
 * exported component/type/util that nothing imports. So dead modules accumulate silently. This walks the static
 * import graph (incl. dynamic `import()` and side-effect imports) from src/app/main.tsx + src/app/App.tsx and
 * reports any reachable-from-nowhere module. Generated `*.gen.*` files are exempt.
 *
 * Bridge entries live under `src/app/` (this project's layout), not `src/`. Tests are not present today; the
 * `isTest` filter keeps the gate forward-compatible with vitest/jest specs when they land.
 *
 * Run: `node scripts/find-orphans.mjs` (wired into `npm run check`). Exit 1 if orphans found.
 *
 * Origin: ported from wb-mqtt-voice config-ui (UI-8). Entries adapted to this project's `src/app/` layout.
 */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const SRC = path.join(ROOT, 'src');
const STATIC_ENTRIES = [
  'src/app/main.tsx',
  'src/app/App.tsx',
  // jest's setupFilesAfterEnv (see jest.config.js); loaded by tooling, not
  // by a static import, so the graph walker can't see it. Same exemption
  // would apply to a vitest setup file if/when the test framework migrates.
  'src/test/setup.ts',
];
const isTest = (f) => /\.(test|spec)\.tsx?$/.test(f);

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    // Ambient declaration files (*.d.ts) are never imported by spec — they augment types globally — so exempt them.
    return e.isDirectory() ? walk(p) : (/\.tsx?$/.test(e.name) && !/\.d\.ts$/.test(e.name) ? [p] : []);
  });
}

function resolveSpec(spec, fromFile) {
  let s = spec.startsWith('@/') ? path.join(SRC, spec.slice(2)) : path.normalize(path.join(path.dirname(fromFile), spec));
  for (const cand of [`${s}.tsx`, `${s}.ts`, path.join(s, 'index.ts'), path.join(s, 'index.tsx'), s]) {
    if (fs.existsSync(cand) && fs.statSync(cand).isFile()) return path.normalize(cand);
  }
  return null;
}

const files = walk(SRC).map((f) => path.normalize(f));
const edges = new Map();
const importRe = /from\s+['"](@\/[^'"]+|\.[^'"]+)['"]/;
const dynRe = /import\(\s*['"](@\/[^'"]+|\.[^'"]+)['"]\s*\)/;
// Side-effect import (no binding): `import './i18n'` — has no `from`, so importRe misses it.
const sideEffectRe = /^\s*import\s+['"](@\/[^'"]+|\.[^'"]+)['"]/;
for (const f of files) {
  const deps = new Set();
  for (const line of fs.readFileSync(f, 'utf8').split('\n')) {
    if (/^\s*\/\//.test(line)) continue;
    for (const re of [importRe, dynRe, sideEffectRe]) {
      const m = line.match(re);
      if (m) { const r = resolveSpec(m[1], f); if (r) deps.add(r); }
    }
  }
  edges.set(f, deps);
}

// Entry points = the app roots PLUS every test file (a module reachable from a test is intentional, not dead).
const seen = new Set();
const stack = [
  ...STATIC_ENTRIES.map((e) => path.normalize(path.join(ROOT, e))),
  ...files.filter(isTest),
];
while (stack.length) {
  const cur = stack.pop();
  if (seen.has(cur)) continue;
  seen.add(cur);
  for (const d of edges.get(cur) ?? []) stack.push(d);
}

const orphans = files.filter((f) => !seen.has(f) && !/\.gen\./.test(f) && !isTest(f)).sort();
if (orphans.length) {
  console.error(`✗ ${orphans.length} orphan module(s) unreachable from the app entries or any test:`);
  for (const o of orphans) console.error(`  ${path.relative(ROOT, o)}`);
  console.error('Wire them up, cover them with a test, delete them, or add an entry in scripts/find-orphans.mjs.');
  process.exit(1);
}
console.log('✓ no orphan modules');

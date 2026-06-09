#!/usr/bin/env node
// Real static-frontend checks for lawapp (replaces the old echo-stub scripts).
//   --lint    : JS syntax check (node --check) on every client/public/js/*.js
//   --assets  : every local src/href in HTML resolves to a real file under client/public
//   (no flag) : run both
// Exits non-zero on ANY failure. No echo-PASS, no || true.
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');   // client/
const PUBLIC = join(ROOT, 'public');
const args = process.argv.slice(2);
const doLint = args.includes('--lint') || args.length === 0;
const doAssets = args.includes('--assets') || args.length === 0;
let failures = 0;
const fail = (m) => { console.error('  [FAIL] ' + m); failures++; };
const pass = (m) => console.log('  [PASS] ' + m);

function walk(dir, ext) {
  const out = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p, ext));
    else if (p.endsWith(ext)) out.push(p);
  }
  return out;
}

if (doLint) {
  console.log('== JS syntax check (node --check) ==');
  const js = existsSync(join(PUBLIC, 'js')) ? walk(join(PUBLIC, 'js'), '.js') : [];
  if (js.length === 0) fail('no JS files found to lint');
  for (const f of js) {
    try { execFileSync(process.execPath, ['--check', f], { stdio: 'pipe' }); pass('syntax ' + f.replace(ROOT + '/', '')); }
    catch (e) { fail('syntax error in ' + f.replace(ROOT + '/', '') + ': ' + (e.stderr?.toString() || e.message).split('\n')[0]); }
  }
}

if (doAssets) {
  console.log('== Asset reference resolution ==');
  const html = walk(PUBLIC, '.html');
  const refRe = /(?:src|href)\s*=\s*"([^"]+)"/g;
  let checked = 0;
  for (const f of html) {
    const txt = readFileSync(f, 'utf8');
    let m;
    while ((m = refRe.exec(txt))) {
      const ref = m[1];
      // skip external, anchors, mailto, and runtime template expressions (${...})
      if (/^(https?:)?\/\//.test(ref) || ref.startsWith('#') || ref.startsWith('mailto:') || ref.includes('${') || ref.trim() === '') continue;
      const rel = ref.split('?')[0].split('#')[0];
      const target = rel === '/' ? join(PUBLIC, 'index.html') : join(PUBLIC, rel.replace(/^\//, ''));
      checked++;
      if (!existsSync(target)) fail(`${f.replace(ROOT + '/', '')} -> broken ref "${ref}"`);
    }
  }
  if (checked === 0) fail('no local asset references found to validate');
  else if (failures === 0) pass(`${checked} local asset references all resolve`);
}

console.log(failures === 0 ? '\nRESULT: PASS' : `\nRESULT: FAIL (${failures} issue(s))`);
process.exit(failures === 0 ? 0 : 1);

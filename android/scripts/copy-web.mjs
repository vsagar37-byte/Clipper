import { cpSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const target = resolve(root, 'www');
rmSync(target, { recursive: true, force: true });
mkdirSync(target, { recursive: true });
cpSync(resolve(root, '../frontend'), target, { recursive: true });
writeFileSync(resolve(target, 'config.js'), 'window.CLIPFORGE_API_URL = "";\n');
console.log('Copied web frontend into Android assets.');
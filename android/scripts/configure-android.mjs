import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
const base = resolve(import.meta.dirname, '..', 'android', 'app', 'src', 'main');
const manifest = resolve(base, 'AndroidManifest.xml');
if (!existsSync(manifest)) { console.error('First run: npm run android:init'); process.exit(1); }
let xml = readFileSync(manifest, 'utf8');
if (!xml.includes('android.permission.INTERNET')) xml=xml.replace('<application', '<uses-permission android:name="android.permission.INTERNET" />\n    <application');
if (!xml.includes('android:usesCleartextTraffic=')) xml=xml.replace(/<application\b/, '<application android:usesCleartextTraffic="true"');
writeFileSync(manifest, xml);
console.log('Enabled LAN HTTP for development. Use HTTPS and remove cleartext permission for production.');